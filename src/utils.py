import crypto

def compare_versions(version1, version2):
    v1 = [int(x) for x in version1.split(".")]
    v2 = [int(x) for x in version2.split(".")]
    for i in range(max(len(v1), len(v2))):
        if i >= len(v1):
            return -1  # version1 is shorter, so it's lower
        elif i >= len(v2):
            return 1   # version2 is shorter, so it's lower
        elif v1[i] < v2[i]:
            return -1  # version1 is lower
        elif v1[i] > v2[i]:
            return 1   # version1 is higher
    return 0           # both versions are equal


def random():
   r = crypto.getrandbits(32)
   return ((r[0]<<24)+(r[1]<<16)+(r[2]<<8)+r[3])/4294967295.0

def random_range(rfrom, rto):
   return random()*(rto-rfrom)+rfrom
