#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#
# This code has been modified by Franco Lopez and Ignacio Fernandez on 03/2023.
# The following code has been altered in order to fullfill our requirements.
# The original code can be found at https://github.com/pycom/pycom-libraries/tree/master/examples/OTA-lorawan

# DISCLAIMER: This code is provided "as is" and without warranty of any kind, express or
# implied, including, but not limited to, the implied warranties of merchantability and
# fitness for a particular purpose. In no event shall the copyright holder or contributors
# be liable for any direct, indirect, incidental, special, exemplary, or consequential
# damages (including, but not limited to, procurement of substitute goods or services;
# loss of use, data, or profits; or business interruption) however caused and on any theory
# of liability, whether in contract, strict liability, or tort (including negligence or
# otherwise) arising in any way out of the use of this software, even if advised of the
# possibility of such damage.

import diff_match_patch as dmp_module
from watchdog import Watchdog
from machine import RTC
import ubinascii
import uhashlib
import _thread
import utime
import uos
import machine
import json
from utils import compare_versions
import uzlib


class LoraOTA:

    MSG_HEADER = b'$OTA'
    MSG_TAIL = b'*'

    FULL_UPDATE = b'F'
    DIFF_UPDATE = b'D'
    NO_UPDATE = b'N'

    DEVICE_VERSION_MSG = 0

    UPDATE_INFO_MSG = 1
    UPDATE_INFO_REPLY = 2

    MULTICAST_KEY_MSG = 3

    LISTENING_MSG = 4

    UPDATE_TYPE_FNAME = 5
    UPDATE_TYPE_PATCH = 6
    UPDATE_TYPE_CHECKSUM = 7

    DELETE_FILE_MSG = 8
    MANIFEST_MSG = 9

    def __init__(self, lora, device_version):
        self.lora = lora
        self.device_version = device_version
        self.update_in_progress = False
        self.operation_timeout = 10
        self.max_send = 5

        self.mcAddr = None
        self.mcNwkSKey = None
        self.mcAppSKey = None

        self.patch = b''
        self.file_to_patch = None
        self.patch_list = dict()
        self.checksum_failure = False
        self.device_mainfest = None

        self._exit = False

        # Watchdog
        self.inactivity_timeout = 60
        self.wdt = Watchdog()
        
        self.lora.init(self.process_message)
        

    def delete_backup_files(self):
        # deleting remaining backup files
        for file in uos.listdir("/flash"):
            if file.endswith(".bak"):
                print("deleting bak file: " + file)
                uos.remove(file)

    def stop(self):
        self.lora.stop()
        self._exit = True

    def change_to_listening_mode(self):
        if self.mcAddr is not None:
            multicast_auth = (self.mcAddr, self.mcNwkSKey, self.mcAppSKey)
            self.lora.change_to_multicast_mode(multicast_auth)
            self.device_mainfest = self.create_device_manifest()

            self.send_listening_msg()

            # iniciar thread para checkear si update failed? como en thread_proc?

        else:
            self.reset_update_params()

    def create_device_manifest(self):

        manifest = dict()
        manifest["delete"] = 0
        manifest["update"] = 0
        manifest["new"] = 0

        return manifest

    def reset_update_params(self):
        self.mcAddr = None
        self.mcNwkSKey = None
        self.mcAppSKey = None

        self.update_version = '0.0.0'

    def send_device_version_message(self):
        # $OTA,0,1.0.1,*
        msg = bytearray()
        msg.extend(self.MSG_HEADER)
        msg.extend(b',' + str(self.DEVICE_VERSION_MSG).encode())
        msg.extend(b',' + self.device_version.encode())
        msg.extend(b',' + self.MSG_TAIL)

        self.lora.send(msg)

    def send_update_info_reply(self):
        # $OTA,2,1.0.1,*
        msg = bytearray()
        msg.extend(self.MSG_HEADER)
        msg.extend(b',' + str(self.UPDATE_INFO_REPLY).encode())
        msg.extend(b',' + self.device_version.encode())
        msg.extend(b',' + self.MSG_TAIL)

        self.lora.send(msg)

    def send_listening_msg(self):
        # $OTA,4,*
        msg = bytearray()
        msg.extend(self.MSG_HEADER)
        msg.extend(b',' + str(self.LISTENING_MSG).encode())
        msg.extend(b',' + self.MSG_TAIL)

        self.lora.send(msg)

    def file_exists(self, file_path):
        exists = False
        try:
            if uos.stat(file_path)[6] > 0:
                exists = True
        except Exception as e:
            exists = False
        return exists

    def get_msg_type(self, msg):
        msg_type = -1
        try:
            msg_type = int(msg.split(b',')[1].decode())
        except Exception as ex:
            print("Exception getting message type")

        return msg_type

    def sync_clock(self, epoc):
        try:
            rtc = RTC()
            rtc.init(utime.gmtime(epoc))
        except Exception as ex:
            print("Exception setting system data/time: {}".format(ex))
            return False

        return True

    def parse_update_info_msg(self, msg):
        # $OTA,1,1.0.2,1674930013,*
        self.resp_received = True

        try:
            token_msg = msg.split(",")
            if compare_versions(token_msg[2], self.device_version) == 1:
                self.update_in_progress = True
                self.update_version = token_msg[2]
                self.wdt.enable(self.inactivity_timeout)
                self.start_watchdog_thread()

            if utime.time() < 1550000000:
                self.sync_clock(int(token_msg[3]))

        except Exception as ex:
            print("Exception getting update information: {}".format(ex))
            return False

        self.send_update_info_reply()

        return True

    def parse_multicast_keys(self, msg):
        # $OTA,3,mcAddr,mcNwkSKey,mcAppSKey,*
        try:
            token_msg = msg.split(",")

            if len(token_msg[2]) > 0:
                self.mcAddr = token_msg[2]
                self.mcNwkSKey = token_msg[3]
                self.mcAppSKey = token_msg[4]

            print("mcAddr: {}, mcNwkSKey: {}, mcAppSKey: {}".format(self.mcAddr, self.mcNwkSKey, self.mcAppSKey))

        except Exception as ex:
            print("Exception getting multicast keys: {}".format(ex))
            return False

        return True

    def get_msg_data(self, msg):
        data = None
        try:
            start_idx = msg.index(",", msg.index(",") + 1) + 1
            stop_idx = msg.rfind(",")
            data = msg[start_idx:stop_idx]
        except Exception as ex:
            print("Exception getting msg data: {}".format(ex))
        return data

    def process_patch_msg(self, msg):
        # $OTA,6, patch_data,*
        partial_patch = msg[7:-2]

        if partial_patch:
            self.patch += partial_patch

    def verify_patch(self, patch, received_checksum):
        h = uhashlib.sha1()
        h.update(patch)
        checksum = ubinascii.hexlify(h.digest()).decode()
        print("Computed checksum: {}".format(checksum))
        print("Received checksum: {}".format(received_checksum))

        if checksum != received_checksum:
            self.checksum_failure = True
            return False

        return True

    def process_checksum_msg(self, msg):
        checksum = self.get_msg_data(msg)
        # Decompress patch
        decompressed_patch = uzlib.decompress(self.patch)
        self.patch = decompressed_patch.decode()
        verified = self.verify_patch(self.patch, checksum)
        if verified:
            self.patch_list[self.file_to_patch] = self.patch

        self.file_to_patch = None
        self.patch = b''

    def backup_file(self, filename):
        bak_path = "{}.bak".format(filename)

        # Delete previous backup if it exists
        try:
            uos.remove(bak_path)
        except OSError:
            pass  # There isnt a previous backup

        # Backup current file
        uos.rename(filename, bak_path)
        
    def del_file(self, filename):
        del_path = "{}.del".format(filename)
        open(del_path, 'w+')  # Create file

    def process_delete_msg(self, msg):
        filename = self.get_msg_data(msg)
        print("Deleting file: {}".format(filename))
        if self.file_exists('/flash/' + filename):
            self.backup_file('/flash/' + filename)
            self.device_mainfest["delete"] += 1

    def get_tmp_filename(self, filename):
        idx = filename.rfind(".")
        return filename[:idx + 1] + "tmp"

    def _read_file(self, filename):

        try:
            with open('/flash/' + filename, 'r') as fh:
                return fh.read()
        except Exception as ex:
            print("Error reading file: {}".format(ex))

        return None

    def _write_to_file(self, filename, text):
        tmp_file = self.get_tmp_filename('/flash/' + filename)

        try:
            with open(tmp_file, 'w+') as fh:
                fh.write(text)
        except Exception as ex:
            print("Error writing to file: {}".format(ex))
            return False

        if self.file_exists('/flash/' + filename):
            self.backup_file('/flash/' + filename)
        else:
            self.del_file('/flash/' + filename)
        uos.rename(tmp_file, '/flash/' + filename)

        return True

    def apply_patches(self):
        for key, value in self.patch_list.items():
            self.dmp = dmp_module.diff_match_patch()
            patches_list = self.dmp.patch_fromText(value)

            to_patch = ''
            print('Updating file: {}'.format(key))
            if self.file_exists('/flash/' + key):
                to_patch = self._read_file(key)

            patched_text, success = self.dmp.patch_apply(patches_list, to_patch)
            if False in success:
                return False

            if not self._write_to_file(key, patched_text):
                return False
        
        print("printing backup files")
        for file in uos.listdir("/flash"):
            if file.endswith(".bak"):
                print(file)

        return True

    @staticmethod
    def find_backups():
        backups = []
        for file in uos.listdir("/flash"):
            if file.endswith(".bak"):
                backups.append(file)
        return backups

    @staticmethod
    def find_dels():
        dels = []
        for file in uos.listdir("/flash"):
            if file.endswith(".del"):
                dels.append(file)
        return dels

    @staticmethod
    def revert():
        backup_list = LoraOTA.find_backups()
        for backup in backup_list:
            idx = backup.find('.bak')
            new_filename = backup[:idx]
            uos.rename(backup, new_filename)
        for del_file in LoraOTA.find_dels():
            idx = del_file.find('.del')
            uos.remove(del_file[:idx])
            uos.remove(del_file)
        print('Error: Reverting to old firmware')
        machine.reset()

    def manifest_failure(self, msg):

        try:
            start_idx = msg.find("{")
            stop_idx = msg.find("}")

            recv_manifest = json.loads(msg[start_idx:stop_idx])

            print("Received manifest: {}".format(recv_manifest))
            print("Actual manifest: {}".format(self.device_mainfest))

            if (recv_manifest["update"] != self.device_mainfest["update"]) or \
               (recv_manifest["new"] != self.device_mainfest["new"]) or \
               (recv_manifest["delete"] != self.device_mainfest["delete"]):
                return True
        except Exception as ex:
            print("Error in manifest: {}".format(ex))
            return True

        return False

    def process_manifest_msg(self, msg):
        if self.manifest_failure(msg):
            print('Manifest failure: Discarding update ...')
            self.reset_update_params()
            machine.reset()
        elif self.checksum_failure:
            print('Failed checksum: Discarding update ...')
            self.reset_update_params()
            machine.reset()
        elif not self.apply_patches():
            LoraOTA.revert()
        else:
            print('Update Success: Restarting .... ')   
            machine.reset()

    def process_filename_msg(self, msg):
        self.file_to_patch = self.get_msg_data(msg)

        if self.file_exists('/flash/' + self.file_to_patch):
            self.device_mainfest["update"] += 1
            print("Update file: {}".format(self.file_to_patch))
        else:
            self.device_mainfest["new"] += 1
            print("Create new file: {}".format(self.file_to_patch))

        self.wdt.enable(self.inactivity_timeout)

    def start_watchdog_thread(self):
        _thread.start_new_thread(self._check_timeout, ())
        
    def _check_timeout(self):
        while True:
            if self.wdt.update_failed():
                
                print("Inactivity timeout: Reverting to old firmware")
                LoraOTA.revert()
            utime.sleep(1)

    def process_message(self, msg):
        self.wdt.ack()

        msg_type = self.get_msg_type(msg)
        if msg_type != self.UPDATE_TYPE_PATCH:
            msg = msg.decode()
        if msg_type == self.UPDATE_INFO_MSG:
            self.parse_update_info_msg(msg)
        elif msg_type == self.MULTICAST_KEY_MSG:
            self.parse_multicast_keys(msg)
            self.change_to_listening_mode()
        elif msg_type == self.UPDATE_TYPE_FNAME:
            self.process_filename_msg(msg)
        elif msg_type == self.UPDATE_TYPE_PATCH:
            self.process_patch_msg(msg)
        elif msg_type == self.UPDATE_TYPE_CHECKSUM:
            self.process_checksum_msg(msg)
        elif msg_type == self.DELETE_FILE_MSG:
            self.process_delete_msg(msg)
        elif msg_type == self.MANIFEST_MSG:
            self.process_manifest_msg(msg)
