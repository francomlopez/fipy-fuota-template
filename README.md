# FiPy FUOTA template

This repository contains an example implementation of Firmware Update Over-The-Air (FUOTA) functionality for Pycom's FiPy IoT development board. The example demonstrates how to update the firmware of FiPy devices wirelessly using the LoRaWAN protocol. The server-side code for handling the FUOTA process is available in a separate repository [lora-fuota-updater](https://github.com/ignacioFernandez1/lora-fuota-updater).

## Prerequisites

To run the example code in this repository, you will need the following:

- A FiPy development board with firmware version 1.20.2.rc9
- A LoRaWAN gateway(Pygate) and network server to handle communication
- A computer with Python 3.x installed

## Getting Started

1. Clone this repository to your local machine

2. Upload src/ files to Fipy device

3. Update the LoRaWAN settings in the `main.py` file to match your specific network setup, including the AppEUI, AppKey, and frequency plan.

4. Implement the server-side code for handling the FUOTA process by referring to the [lora-fuota-updater](https://github.com/ignacioFernandez1/lora-fuota-updater). This repository only contains the code that needs to be uploaded to the Pycom device.

The example code implements the FUOTA process on the Pycom device, which includes sending a firmware update request to the LoRaWAN network server, receiving the update payload, and applying the firmware update to the FiPy device.

## Contributing

If you would like to contribute to this project, please follow the standard GitHub workflow for forking the repository, creating a branch, making changes, and submitting a pull request. We welcome contributions from the community to improve the functionality and reliability of this example code.

## License

This example code is released under the GNU General Public License (GPL) version 3, which allows for free use, modification, and distribution, but comes with certain restrictions and obligations. Please refer to the [LICENSE](LICENSE) file for more information.

## Acknowledgements

This example code is based on the Pycom documentation and LoRaWAN specification. We acknowledge the contributions of the Pycom community and the LoRaWAN community in developing this example code. Special thanks to the Pycom team for creating the FiPy development board and supporting the IoT community.

## Contact

If you have any questions, comments, or suggestions, please feel free to contact us at [francomlopez@mi.unc.edu.ar](mailto:francomlopez@mi.unc.edu.ar) or at [ignacio.fernandez@mi.unc.edu.ar](mailto:ignacio.fernandez@mi.unc.edu.ar).

