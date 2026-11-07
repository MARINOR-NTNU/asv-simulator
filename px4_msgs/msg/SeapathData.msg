# Kongsberg Seapath data (Seapath Binary 26 frame), decoded to SI units.
# Signs follow the Seapath, which matches PX4's NED / FRD conventions.

uint64 timestamp                    # time since system start (microseconds)
uint64 timestamp_sample             # estimated time the data was valid (microseconds)

uint64 time_utc_usec                # Seapath UTC time (microseconds since 1970)

float64 latitude_deg                # [deg] positive north
float64 longitude_deg               # [deg] positive east
float32 height_ellipsoid_m          # [m] above the WGS84 ellipsoid

float32 vel_n_m_s                   # [m/s]
float32 vel_e_m_s                   # [m/s]
float32 vel_d_m_s                   # [m/s] positive down

float32 roll_rad                    # [rad] positive port side up
float32 pitch_rad                   # [rad] positive bow up
float32 heading_rad                 # [rad] true heading, 0 to 2*pi

float32 roll_rate_rad_s             # [rad/s]
float32 pitch_rate_rad_s            # [rad/s]
float32 yaw_rate_rad_s              # [rad/s] positive clockwise seen from above

float32 heave_m                     # [m] real-time heave, positive down
uint64 delayed_heave_time_utc_usec  # UTC time of the delayed heave value (microseconds)
float32 delayed_heave_m             # [m] positive down

uint16 status                       # raw status word (1 = true). HORIZ = horizontal position and velocity, VERT = heave and vertical velocity
uint16 STATUS_HORIZ_REDUCED = 1
uint16 STATUS_HORIZ_INVALID = 2
uint16 STATUS_VERT_REDUCED = 4
uint16 STATUS_VERT_INVALID = 8
uint16 STATUS_RP_REDUCED = 16
uint16 STATUS_RP_INVALID = 32
uint16 STATUS_HEADING_REDUCED = 64
uint16 STATUS_HEADING_INVALID = 128
uint16 STATUS_DELAYED_HEAVE_INVALID = 256
