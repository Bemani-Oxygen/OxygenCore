from typing_extensions import Final


class GameConstants:
    IIDX: Final[str] = 'iidx'


class APIConstants:
    ID_TYPE_SERVER: Final[str] = 'server'
    ID_TYPE_CARD: Final[str] = 'card'
    ID_TYPE_SONG: Final[str] = 'song'
    ID_TYPE_INSTANCE: Final[str] = 'instance'


class DBConstants:
    # When adding new game series, I try to make sure that constants
    # go in order, and have a difference of 100 between them. This is
    # so I can promote lamps/scores/etc by using a simple "max", while
    # still allowing for new game versions to insert new constants anywhere
    # in the lineup. You'll notice a few areas where constants go up by
    # non-100. This is because a new game came out in this series after
    # existing scores were in production, so constants for new grades/lamps
    # had to be snuck in. The actual constant doesn't matter as long as they
    # go in order, so this works out nicely.

    # Its up to various games to map the in-game constant to these DB
    # constants. Most games will implement a pair of functions that takes
    # one of these values and spits out the game-specific constant, and
    # vice versa. This keeps us individual game agnostic and allows us to
    # react easily to renumberings and constant insertions. These constants
    # will only be found in the DB itself, as well as used on the frontend
    # to display various general information about scores.

    OMNIMIX_VERSION_BUMP: Final[int] = 10000

    IIDX_CLEAR_STATUS_NO_PLAY: Final[int] = 50
    IIDX_CLEAR_STATUS_FAILED: Final[int] = 100
    IIDX_CLEAR_STATUS_ASSIST_CLEAR: Final[int] = 200
    IIDX_CLEAR_STATUS_EASY_CLEAR: Final[int] = 300
    IIDX_CLEAR_STATUS_CLEAR: Final[int] = 400
    IIDX_CLEAR_STATUS_HARD_CLEAR: Final[int] = 500
    IIDX_CLEAR_STATUS_EX_HARD_CLEAR: Final[int] = 600
    IIDX_CLEAR_STATUS_FULL_COMBO: Final[int] = 700
    IIDX_DAN_RANK_7_KYU: Final[int] = 100
    IIDX_DAN_RANK_6_KYU: Final[int] = 200
    IIDX_DAN_RANK_5_KYU: Final[int] = 300
    IIDX_DAN_RANK_4_KYU: Final[int] = 400
    IIDX_DAN_RANK_3_KYU: Final[int] = 500
    IIDX_DAN_RANK_2_KYU: Final[int] = 600
    IIDX_DAN_RANK_1_KYU: Final[int] = 700
    IIDX_DAN_RANK_1_DAN: Final[int] = 800
    IIDX_DAN_RANK_2_DAN: Final[int] = 900
    IIDX_DAN_RANK_3_DAN: Final[int] = 1000
    IIDX_DAN_RANK_4_DAN: Final[int] = 1100
    IIDX_DAN_RANK_5_DAN: Final[int] = 1200
    IIDX_DAN_RANK_6_DAN: Final[int] = 1300
    IIDX_DAN_RANK_7_DAN: Final[int] = 1400
    IIDX_DAN_RANK_8_DAN: Final[int] = 1500
    IIDX_DAN_RANK_9_DAN: Final[int] = 1600
    IIDX_DAN_RANK_10_DAN: Final[int] = 1700
    IIDX_DAN_RANK_CHUDEN: Final[int] = 1800
    IIDX_DAN_RANK_KAIDEN: Final[int] = 1900
