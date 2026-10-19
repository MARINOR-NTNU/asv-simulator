uint64 timestamp						# time since system start (microseconds)

uint8 VEL_STICK_INDEX = 0
uint8 HEADING_STICK_INDEX = 1

uint8 SURGE_STICK_INDEX = 0
uint8 SWAY_STICK_INDEX = 1
uint8 YAW_STICK_INDEX = 2

uint8 FORWARD_PROPELLER_STICK_INDEX = 0
uint8 PORT_SIDE_THRUST_STICK_INDEX = 1
uint8 STYRBORD_MOTOR_THRUST_STICK_INDEX = 2
uint8 MOTORS_ANGLE_STICK_INDEX = 3

uint8 AUTOMATIC_MODE = 4
uint8 VEL_HEADING_MODE = 5
uint8 WRENCH_MODE = 6
uint8 MOTOR_OUTPUT_MODE = 7

# uint8 SA_STICK Undefined
uint8 SB_STICK = 5
uint8 SC_STICK = 6
uint8 SD_STICK = 7
uint8 SE_STICK = 8
uint8 SF_STICK = 9

uint8 mode
uint16[4] thruster_values
bool is_armed
