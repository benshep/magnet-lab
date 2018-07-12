import ctypes
import enum
from math import log2


class EncoderException(Exception):
    """Raise when an exception happens relating to the Adlink encoder card."""


# function to check for valid return codes
err_codes = {-10000: "Card number", -10001: "operation system version", -10002: "card’s ID conflict",
             -10200: "other process exist", -10201: "card not found", -10202: "Open driver failed",
             -10203: "ID mapping failed", -10204: "trigger channel", -10205: "trigger type",
             -10206: "event already enabled", -10207: "event not enable yet", -10208: "on board FIFO full",
             -10209: "unknown command type", -10210: "unknown chip type", -10211: "card not initial",
             -10212: "position out of range", -10213: "motion busy", -10214: "speed error",
             -10215: "slow down point", -10216: "axis range error", -10217: "compare parameter error",
             -10218: "compare method", -10219: "axis already stop", -10220: "axis INT wait failed",
             -10221: "user code write failed", -10222: "array size exceed", -10223: "factor number",
             -10224: "enable range", -10225: "auto accelerate time", -10226: "dwell time",
             -10227: "dwell distance", -10228: "new position", -10229: "motion not in running",
             -10230: "velocity change time", -10231: "speed target", -10232: "velocity percent",
             -10233: "position change backward", -10234: "counter number"}


def CheckSuccess(result, func, arguments):
    if not result == 0:
        raise EncoderException(f'function {func.__name__} failed with error code {result} "{err_codes[result]}"')
    else:
        return result


class InterruptFactor(enum.IntFlag):
    """Enumeration of interrupt factors used by set_motion_int_factor."""
    NORMAL_STOP = enum.auto()
    STARTING_THE_NEXT_OPERATION_CONTINUOUSLY = enum.auto()
    WRITING_TO_THE_2ND_PRE_REGISTER = enum.auto()
    WRITING_TO_THE_2ND_PRE_REGISTER_FOR_TRIGGER_COMPARATOR = enum.auto()
    START_ACCELERATION = enum.auto()
    ACCELERATION_END = enum.auto()
    START_DECELERATION = enum.auto()
    DECELERATION_END = enum.auto()
    WHEN_SOFT_LIMIT_TURN_ON_POSITIVE_DIRECTION = enum.auto()
    WHEN_SOFT_LIMIT_TURN_ON_NEGATIVE_DIRECTION = enum.auto()
    WHEN_ERROR_COMPARATOR_CONDITIONS_ARE_MET = enum.auto()
    WHEN_GENERAL_COMPARATOR_CONDITIONS_ARE_MET = enum.auto()
    WHEN_TRIGGER_COMPARATOR_CONDITIONS_ARE_MET = enum.auto()
    WHEN_RESETTING_THE_COUNT_VALUE_WITH_A_CLR_SIGNAL_INPUT = enum.auto()
    WHEN_LATCHING_THE_COUNT_VALUE_WITH_A_LTC_SIGNAL_INPUT = enum.auto()
    WHEN_LATCHING_THE_COUNT_VALUE_WITH_AN_ORG_SIGNAL_INPUT = enum.auto()
    WHEN_THE_SD_INPUT_IS_ON = enum.auto()
    WHEN_THE_DR_INPUT_IS_CHANGED = enum.auto()
    WHEN_THE_CSTA_INPUT_IS_ON = enum.auto()


class ComparingSource(enum.IntEnum):
    """Enumeration of comparing source for set_trigger_comparator."""
    COMMAND_COUNTER = 0
    FEEDBACK_COUNTER = 1
    ERROR_COUNTER = 2
    GENERAL_COUNTER = 3


class CompareMethod(enum.IntEnum):
    """Enumeration of comparison method for set_trigger_comparator."""
    DATA_EQ_SOURCE_COUNTER_DIRECTION_INDEPENDENT = 1
    DATA_EQ_SOURCE_COUNTER_COUNT_UP_ONLY = 2
    DATA_EQ_SOURCE_COUNTER_COUNT_DOWN_ONLY = 3
    DATA_GT_SOURCE_COUNTER = 4
    DATA_LT_SOURCE_COUNTER = 5


class Axis:
    """Functions for a particular encoder axis."""

    def __init__(self, dll, axis_id, card_id):
        self.dll = dll
        self.id = axis_id
        self.card_id = card_id
        self.setInterruptFactor(InterruptFactor.WHEN_TRIGGER_COMPARATOR_CONDITIONS_ARE_MET)
        self.setInterruptControl(True)

    def setPosition(self, position):
        """Set the encoder position returned by the card."""
        self.dll._8102_set_position(self.id, position)

    def getPosition(self):
        """Return the encoder position given by the card."""
        pos = ctypes.c_double(0)
        self.dll._8102_get_position(self.id, pos)
        return pos.value

    def setInterruptFactor(self, int_factor):
        """Set the motion interrupt factor."""
        self.dll._8102_set_motion_int_factor(self.id, int_factor)

    def setTriggerPosition(self, source, method, data):
        """Set the encoder position to compare with in order to generate a trigger."""
        self.dll._8102_set_trigger_comparator(self.id, source, method, int(data))

    def setInterruptControl(self, int_control=True):
        """Enable/disable the Windows interrupt control for the card."""
        self.dll._8102_int_control(self.card_id, int(int_control))

    def waitForInterrupt(self, int_factor_bit, timeout=10000):
        """Wait for the encoder to generate a trigger event. Timeout in milliseconds."""
        self.dll._8102_wait_motion_interrupt(self.id, int(int_factor_bit), int(timeout))

    def waitForPosition(self, position, timeout=10000):
        """Wait for the encoder to reach a given position. Timeout in milliseconds."""
        self.setTriggerPosition(ComparingSource.FEEDBACK_COUNTER,
                                CompareMethod.DATA_EQ_SOURCE_COUNTER_DIRECTION_INDEPENDENT, position)
        self.waitForInterrupt(log2(InterruptFactor.WHEN_TRIGGER_COMPARATOR_CONDITIONS_ARE_MET), timeout)


class AdlinkCard:
    """Class to handle communications with the ADLINK encoder reader card. This allows us to get encoder output
    and use it to trigger Hall probe readings when the encoder passes given values."""

    def __init__(self):
        dll = ctypes.WinDLL(r'C:\Program Files\ADLINK\PCI-8102\Library\8102.dll')
        # set up return and argument types for functions we're interested in
        funcs = {'initial': [ctypes.POINTER(ctypes.c_uint16), ctypes.c_int16],
                 'config_from_file': None,
                 'set_position': [ctypes.c_int16, ctypes.c_double],
                 'get_position': [ctypes.c_int16, ctypes.POINTER(ctypes.c_double)],
                 'set_motion_int_factor': [ctypes.c_int16, ctypes.c_uint32],
                 'set_trigger_comparator': [ctypes.c_int16, ctypes.c_int16, ctypes.c_int16, ctypes.c_int32],
                 'wait_motion_interrupt': [ctypes.c_int16, ctypes.c_int16, ctypes.c_int32],
                 'int_control': [ctypes.c_int16, ctypes.c_int16]}

        for func_name, arg_types in funcs.items():
            func = getattr(dll, '_8102_' + func_name)
            func.restype = ctypes.c_int16
            func.argtypes = arg_types
            func.errcheck = CheckSuccess

        card_id = ctypes.c_uint16(0)
        # _8102_initial(U16 *CardID_InBit, I16 Manual_ID)
        # Manual_ID: The CardID could be decided by :
        #    0: the sequence of PCI slot.
        #    1: on board DIP switch (SW1)
        dll._8102_initial(card_id, 0)
        dll._8102_config_from_file()  # set from C:\Windows\System32\8102.ini - use MotionCreatorPro to alter

        self.axis = {'z': Axis(dll, 0, card_id=0)}
