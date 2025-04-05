import argparse
import datetime
import logging
import os
import queue
import select
import socket
import struct
import threading
import time

logger = logging.getLogger("NTP Server")


class NTPException(Exception):
    """Exception raised by this module."""

    pass


class NTP:
    """Helper class defining constants."""

    _SYSTEM_EPOCH = datetime.datetime(*time.gmtime(0)[0:3])
    """system epoch"""
    _NTP_EPOCH = datetime.datetime(1900, 1, 1)
    """NTP epoch"""
    NTP_DELTA = int((_SYSTEM_EPOCH - _NTP_EPOCH).total_seconds())
    """delta between system and NTP time"""

    REF_ID_TABLE = {
        "DNC": "DNC routing protocol",
        "NIST": "NIST public modem",
        "TSP": "TSP time protocol",
        "DTS": "Digital Time Service",
        "ATOM": "Atomic clock (calibrated)",
        "VLF": "VLF radio (OMEGA, etc)",
        "callsign": "Generic radio",
        "LORC": "LORAN-C radionavidation",
        "GOES": "GOES UHF environment satellite",
        "GPS": "GPS UHF satellite positioning",
    }
    """reference identifier table"""

    STRATUM_TABLE = {
        0: "unspecified",
        1: "primary reference",
    }
    """stratum table"""

    MODE_TABLE = {
        0: "unspecified",
        1: "symmetric active",
        2: "symmetric passive",
        3: "client",
        4: "server",
        5: "broadcast",
        6: "reserved for NTP control messages",
        7: "reserved for private use",
    }
    """mode table"""

    LEAP_TABLE = {
        0: "no warning",
        1: "last minute has 61 seconds",
        2: "last minute has 59 seconds",
        3: "alarm condition (clock not synchronized)",
    }
    """leap indicator table"""

    @classmethod
    def system_to_ntp_time(cls, timestamp):
        """Convert a system time to a NTP time.

        Parameters:
        timestamp -- timestamp in system time

        Returns:
        corresponding NTP time
        """
        return timestamp + cls.NTP_DELTA


class NTPPacket:
    """NTP packet class.

    This represents an NTP packet.
    """

    _PACKET_FORMAT = "!B B B b 11I"
    """packet format to pack/unpack"""

    def __init__(self, version=2, mode=3):
        """Constructor.

        Parameters:
        version      -- NTP version
        mode         -- packet mode (client, server)
        """
        self.leap = 0
        """leap second indicator"""
        self.version = version
        """version"""
        self.mode = mode
        """mode"""
        self.stratum = 0
        """stratum"""
        self.poll = 0
        """poll interval"""
        self.precision = 0
        """precision"""
        self.root_delay = 0
        """root delay"""
        self.root_dispersion = 0
        """root dispersion"""
        self.ref_id = 0
        """reference clock identifier"""
        self.ref_timestamp_high = 0
        self.ref_timestamp_low = 0
        """reference timestamp"""
        self.orig_timestamp_high = 0
        self.orig_timestamp_low = 0
        """originate timestamp"""
        self.recv_timestamp_high = 0
        self.recv_timestamp_low = 0
        """receive timestamp"""
        self.tx_timestamp_high = 0
        self.tx_timestamp_low = 0
        """tansmit timestamp"""

    @classmethod
    def _to_int(cls, timestamp):
        """Return the integral part of a timestamp.

        Parameters:
        timestamp -- NTP timestamp

        Retuns:
        integral part
        """
        return int(timestamp)

    @classmethod
    def _to_frac(cls, timestamp, n=32):
        """Return the fractional part of a timestamp.

        Parameters:
        timestamp -- NTP timestamp
        n         -- number of bits of the fractional part

        Retuns:
        fractional part
        """
        return int(abs(timestamp - cls._to_int(timestamp)) * 2**n)

    @classmethod
    def _to_time(cls, integ, frac, n=32):
        """Return a timestamp from an integral and fractional part.

        Parameters:
        integ -- integral part
        frac  -- fractional part
        n     -- number of bits of the fractional part

        Retuns:
        timestamp
        """
        return integ + float(frac) / 2**n

    def to_data(self):
        """Convert this NTPPacket to a buffer that can be sent over a socket.

        Returns:
        buffer representing this packet

        Raises:
        NTPException -- in case of invalid field
        """
        try:
            packed = struct.pack(
                self._PACKET_FORMAT,
                (self.leap << 6 | self.version << 3 | self.mode),
                self.stratum,
                self.poll,
                self.precision,
                self._to_int(self.root_delay) << 16
                | self._to_frac(self.root_delay, 16),
                self._to_int(self.root_dispersion) << 16
                | self._to_frac(self.root_dispersion, 16),
                self.ref_id,
                self.ref_timestamp_high,
                self.ref_timestamp_low,
                self.orig_timestamp_high,
                self.orig_timestamp_low,
                self.recv_timestamp_high,
                self.recv_timestamp_low,
                self.tx_timestamp_high,
                self.tx_timestamp_low,
            )

        except struct.error:
            raise NTPException("Invalid NTP packet fields.")
        return packed

    def from_data(self, data):
        """Populate this instance from a NTP packet payload received from
        the network.

        Parameters:
        data -- buffer payload

        Raises:
        NTPException -- in case of invalid packet format
        """
        try:
            unpacked = struct.unpack(
                self._PACKET_FORMAT,
                data[0 : struct.calcsize(self._PACKET_FORMAT)],
            )
        except struct.error:
            raise NTPException("Invalid NTP packet.")

        self.leap = unpacked[0] >> 6 & 0x3
        self.version = unpacked[0] >> 3 & 0x7
        self.mode = unpacked[0] & 0x7
        self.stratum = unpacked[1]
        self.poll = unpacked[2]
        self.precision = unpacked[3]
        self.root_delay = float(unpacked[4]) / 2**16
        self.root_dispersion = float(unpacked[5]) / 2**16
        self.ref_id = unpacked[6]
        self.ref_timestamp_high = unpacked[7]
        self.ref_timestamp_low = unpacked[8]
        self.orig_timestamp_high = unpacked[9]
        self.orig_timestamp_low = unpacked[10]
        self.recv_timestamp_high = unpacked[11]
        self.recv_timestamp_low = unpacked[12]
        self.tx_timestamp_high = unpacked[13]
        self.tx_timestamp_low = unpacked[14]

    def set_orig_timestamp(self, ntp_timestamp):
        """Set the originate timestamp.

        Parameters:
        timestamp -- originate
        """
        self.orig_timestamp_high = self._to_int(ntp_timestamp)
        self.orig_timestamp_low = self._to_frac(ntp_timestamp)

    def set_ref_timestamp(self, ntp_timestamp):
        """Set the reference timestamp.

        Parameters:
        timestamp -- reference timestamp
        """
        self.ref_timestamp_high = self._to_int(ntp_timestamp)
        self.ref_timestamp_low = self._to_frac(ntp_timestamp)

    def set_recv_timestamp(self, ntp_timestamp):
        """Set the receive timestamp.

        Parameters:
        timestamp -- receive timestamp
        """
        self.recv_timestamp_high = self._to_int(ntp_timestamp)
        self.recv_timestamp_low = self._to_frac(ntp_timestamp)

    def set_tx_timestamp(self, ntp_timestamp):
        """Set the transmit timestamp.

        Parameters:
        timestamp -- transmit
        """
        self.tx_timestamp_high = self._to_int(ntp_timestamp)
        self.tx_timestamp_low = self._to_frac(ntp_timestamp)


class RecvThread(threading.Thread):
    """Thread for receiving NTP packets."""

    def __init__(self, socket, taskQueue, stop_event):
        """Initialize receive thread.

        Parameters:
        socket -- socket to receive from
        taskQueue -- queue to put received packets in
        stop_event -- event to signal thread to stop
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self.socket = socket
        self.taskQueue = taskQueue
        self.stop_event = stop_event

    def run(self):
        """Run the receive thread."""
        while not self.stop_event.is_set():
            rlist, wlist, elist = select.select([self.socket], [], [], 1)
            if not rlist:
                continue

            for tempSocket in rlist:
                try:
                    recvTimestamp = NTP.system_to_ntp_time(time.time())
                    data, addr = tempSocket.recvfrom(1024)
                    self.taskQueue.put((data, addr, recvTimestamp))
                    logger.debug(
                        f"Received packet from {addr[0]}:{addr[1]} at {recvTimestamp}"
                    )
                except Exception as e:
                    logger.error(f"Error receiving data from {addr[0]}:{addr[1]}: {e}")


class SendThread(threading.Thread):
    """Thread for sending NTP responses."""

    def __init__(
        self, socket, taskQueue, stop_event, ref_id, stratum=2, offset=0, leap=0
    ):
        """Initialize send thread.

        Parameters:
        socket -- socket to send from
        taskQueue -- queue to get packets from
        stop_event -- event to signal thread to stop
        ref_id -- reference ID for NTP server
        stratum -- stratum level of server
        offset -- time offset in seconds
        leap -- leap second indicator
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self.socket = socket
        self.taskQueue = taskQueue
        self.stop_event = stop_event
        self.leap = leap
        self.stratum = stratum
        self.offset = offset
        self.ref_id = ref_id

    def run(self):
        """Run the send thread."""
        while not self.stop_event.is_set():
            try:
                data, addr, recvTimestamp = self.taskQueue.get(timeout=1)
            except queue.Empty:
                continue

            recvPacket = NTPPacket()

            try:
                recvPacket.from_data(data)
                sendPacket = NTPPacket(version=3, mode=4)
                sendPacket.stratum = self.stratum
                sendPacket.poll = recvPacket.poll
                sendPacket.ref_id = self.ref_id
                sendPacket.leap = self.leap
                sendPacket.orig_timestamp_high = recvPacket.tx_timestamp_high
                sendPacket.orig_timestamp_low = recvPacket.tx_timestamp_low
                sendPacket.set_ref_timestamp(recvTimestamp)
                sendPacket.set_recv_timestamp(recvTimestamp + self.offset)
                sendPacket.set_tx_timestamp(
                    NTP.system_to_ntp_time(time.time() + self.offset)
                )
                send_data = sendPacket.to_data()
            except NTPException as e:
                logger.error(f"Error processing NTP packet: {e}")
                continue

            try:
                self.socket.sendto(send_data, addr)
                logger.info(f"Responded to {addr[0]}:{addr[1]}")
            except Exception as e:
                logger.error(f"Failed to send response to {addr[0]}:{addr[1]}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NTP server")
    parser.add_argument("--ip", default="0.0.0.0", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=123, help="Port to bind to")
    parser.add_argument(
        "--ref_id",
        type=lambda x: int(x, 0) if x.startswith(("0x", "0b", "0o")) else int(x),
        default=int.from_bytes(os.urandom(4), byteorder="big"),
        help="Reference ID (4-byte integer, can be hex with 0x prefix). The default is a random 4-byte integer.",
    )
    parser.add_argument("--offset", type=int, default=0, help="Time offset")
    parser.add_argument("--stratum", type=int, default=2, help="NTP stratum")
    parser.add_argument("--leap", type=int, default=0, help="Leap second indicator")
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logger.info(f"NTP server started on {args.ip}:{args.port}")
    logger.info(f"Stratum: {args.stratum}")
    logger.info(f"Time offset: {args.offset} seconds")
    logger.info(f"Reference ID: 0x{args.ref_id:08x}")

    logger.info(
        f"Leap second indicator: {args.leap}: {NTP.LEAP_TABLE.get(int(args.leap), 'Unknown')}"
    )

    logger.info("Press Ctrl+C to exit")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind((args.ip, args.port))

        taskQueue = queue.Queue()
        stop_event = threading.Event()

        recvThread = RecvThread(server_socket, taskQueue, stop_event)
        recvThread.start()

        workThread = SendThread(
            server_socket,
            taskQueue,
            stop_event,
            args.ref_id,
            args.stratum,
            args.offset,
            args.leap,
        )

        workThread.start()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_event.set()
            logger.info("Closing NTP server...")
            recvThread.join()
            workThread.join()
            logger.info("NTP server stopped.")
