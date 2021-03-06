import traceback
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Type

from .common import Model, ValidatedDict, Time
from .data import Data, UserID


class ProfileCreationException(Exception):
    pass


class Status:
    """
    List of statuses we return to the game for various reasons.
    """
    SUCCESS = 0
    NO_PROFILE = 109
    NOT_ALLOWED = 110
    NOT_REGISTERED = 112
    INVALID_PIN = 116


class Factory:
    """
    The base class every game factory inherits from. Defines a create method
    which should return some game class which can handle packets. Game classes
    inherit from Base, and have handle_<call>_request methods on them that
    Dispatch will look up in order to handle calls.
    """

    MANAGED_CLASSES: List[Type["Base"]] = []

    @classmethod
    def register_all(cls) -> None:
        """
        Subclasses of this class should use this function to register themselves
        with Base, using Base.register(). Factories specify the game code that
        they support, which Base will use when routing requests.
        """
        raise Exception('Override this in subclass!')

    @classmethod
    async def run_scheduled_work(cls, data: Data, config: Dict[str, Any]) -> None:
        """
        Subclasses of this class should use this function to run any scheduled
        work on classes which it is a factory for. This is usually used for
        out-of-band DB operations such as generating new weekly/daily charts,
        calculating league scores, etc.
        """
        for game in cls.MANAGED_CLASSES:
            try:
                events = await game.run_scheduled_work(data, config)
            except Exception:
                events = []
                stack = traceback.format_exc()
                print(stack)
                await data.local.network.put_event(
                    'exception',
                    {
                        'service': 'scheduler',
                        'traceback': stack,
                    },
                )
            for event in events:
                await data.local.network.put_event(event[0], event[1])

    @classmethod
    def all_games(cls) -> Iterator[Tuple[str, int, str]]:
        """
        Given a particular factory, iterate over all game, version combinations.
        Useful for loading things from the DB without wanting to hardcode values.
        """
        for game in cls.MANAGED_CLASSES:
            yield (game.game, game.version, game.name)

    @classmethod
    def all_settings(cls) -> Iterator[Tuple[str, int, Dict[str, Any]]]:
        """
        Given a particular factory, iterate over all game, version combinations that
        have settings and return those settings.
        """
        for game in cls.MANAGED_CLASSES:
            yield (game.game, game.version, game.get_settings())

    @classmethod
    def create(cls, data: Data, config: Dict[str, Any], model: Model, parentmodel: Optional[Model] = None) -> Optional['Base']:
        """
        Given a modelstring and an optional parent model, return an instantiated game class that can handle a packet.

        Parameters:
            data - A Data singleton for DB access
            config - Configuration dictionary
            model - A parsed Model, used by game factories to determine which game class to return
            parentmodel - The parent model doing the requesting. In some cases, games request an older
                          version game class to migrate profiles. This presents a problem when they don't
                          specify version strings, because some game lookups are ambiguous without them.
                          This allows a factory to determine which game to return based on the parent
                          requesting model, assuming that we want one version back.

        Returns:
            A subclass of Base that hopefully has a handle_<call>_request method on it, for the particular
            call that Dispatch wants to resolve, or None if we can't look up a game.
        """
        raise Exception('Override this in subclass!')


class Base:
    """
    The base class every game class inherits from. Incudes handlers for card management, PASELI, most
    non-game startup packets, and simple code for loading/storing profiles.
    """

    __registered_games: Dict[str, Type[Factory]] = {}
    __registered_handlers: Set[Type[Factory]] = set()

    """
    Override this in your subclass.
    """
    game = 'dummy'

    """
    Override this in your subclass.
    """
    version = 0

    """
    Override this in your subclass.
    """
    name = 'dummy'

    def __init__(self, data: Data, config: Dict[str, Any], model: Model) -> None:
        self.data = data
        self.config = config
        self.model = model

    @classmethod
    def create(cls, data: Data, config: Dict[str, Any], model: Model, parentmodel: Optional[Model] = None) -> Optional['Base']:
        """
        Given a modelstring and an optional parent model, return an instantiated game class that can handle a packet.

        Note that this is provided here as game factories register with Base to advertise that the will
        handle some model string. This allows game code to ask for other game classes by model only.

        Parameters:
            data - A Data singleton for DB access
            config - Configuration dictionary
            model - A parsed Model, used by game factories to determine which game class to return
            parentmodel - The parent model doing the requesting. In some cases, games request an older
                          version game class to migrate profiles. This presents a problem when they don't
                          specify version strings, because some game lookups are ambiguous without them.
                          This allows a factory to determine which game to return based on the parent
                          requesting model, assuming that we want one version back.

        Returns:
            A subclass of Base that hopefully has a handle_<call>_request method on it, for the particular
            call that Dispatch wants to resolve, or an instance of Base itself if no game is registered for
            this model. Its possible to return None from this function if a registered game has no way of
            handling this particular modelstring.
        """
        if model.game not in cls.__registered_games:
            # Return just this base model, which will provide nothing
            return Base(data, config, model)
        else:
            # Return the registered module providing this game
            return cls.__registered_games[model.game].create(data, config, model, parentmodel=parentmodel)

    @classmethod
    def register(cls, game: str, handler: Type[Factory]) -> None:
        """
        Register a factory to handle a game. Note that the game should be the game
        code as returned by a game, such as "LDJ" or "MDX".

        Parameters:
            game - 3-character string identifying a game
            handler - A factory which has a create() method that can spawn game classes.
        """
        cls.__registered_games[game] = handler
        cls.__registered_handlers.add(handler)

    @classmethod
    def run_scheduled_work(cls, data: Data, config: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Run any out-of-band scheduled work that is applicable to this game.
        """
        return []

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        """
        Return any game settings this game wishes a front-end to modify.
        """
        return {}

    @classmethod
    def all_games(cls) -> Iterator[Tuple[str, int, str]]:
        """
        Given all registered factories, iterate over all game, version combinations.
        Useful for loading things from the DB without wanting to hardcode values.
        """
        for factory in cls.__registered_handlers:
            for game in factory.MANAGED_CLASSES:
                yield (game.game, game.version, game.name)

    @classmethod
    def all_settings(cls) -> Iterator[Tuple[str, int, Dict[str, Any]]]:
        """
        Given all registered factories, iterate over all game, version combinations that
        have settings and return those settings.
        """
        for factory in cls.__registered_handlers:
            for game in factory.MANAGED_CLASSES:
                yield (game.game, game.version, game.get_settings())

    def extra_services(self) -> List[str]:
        """
        A list of extra services that this game needs to advertise.
        Override in your subclass if you need to advertise extra
        services for a particular game or series.
        """
        return []

    def supports_paseli(self) -> bool:
        """
        An override so that particular games can disable PASELI support
        regardless of the server settings. Some games and some regions
        are buggy with respect to PASELI.
        """
        return True

    def bind_profile(self, userid: UserID) -> None:
        """
        Handling binding the user's profile to this version on this server.

        Parameters:
            userid - The user ID we are binding the profile for.
        """

    async def has_profile(self, userid: UserID) -> bool:
        """
        Return whether a user has a profile for this game/version on this server.

        Parameters:
            userid - The user ID we are binding the profile for.

        Returns:
            True if the profile exists, False if not.
        """
        return await self.data.local.user.get_profile(self.game, self.version, userid) is not None

    async def get_profile(self, userid: UserID) -> Optional[ValidatedDict]:
        """
        Return the profile for a user given this game/version on any connected server.

        Parameters:
            userid - The user ID we are getting the profile for.

        Returns:
            A dictionary representing the user's profile, or None if it doesn't exist.
        """
        return await self.data.local.user.get_profile(self.game, self.version, userid)

    async def get_any_profile(self, userid: UserID) -> ValidatedDict:
        """
        Return ANY profile for a user in a game series.

        Tries to look up the profile for a userid/game/version on any connected server.
        If that fails, looks for the latest profile that the user has for the current
        game series. This is usually used for fetching profiles to display names for
        scores, as users can earn scores on different mixes of games and on remote
        networks.

        Parameters:
            userid - The user ID we are getting the profile for.

        Returns:
            A dictionary representing the user's profile, or an empty dictionary if
            none was found.
        """
        profile = await self.data.local.user.get_any_profile(self.game, self.version, userid)
        if profile is None:
            profile = ValidatedDict()
        return profile

    async def get_any_profiles(self, userids: List[UserID]) -> List[Tuple[UserID, ValidatedDict]]:
        """
        Does the identical thing to the above function, but takes a list of user IDs to
        fetch in bulk.

        Parameters:
            userids - List of user IDs we are getting the profile for.

        Returns:
            A list of tuples with the User ID and dictionary representing the user's profile,
            or an empty dictionary if nothing was found.
        """
        userids = list(set(userids))
        profiles = await self.data.local.user.get_any_profiles(self.game, self.version, userids)
        return [
            (userid, profile if profile is not None else ValidatedDict())
            for (userid, profile) in profiles
        ]

    async def put_profile(self, userid: UserID, profile: ValidatedDict) -> None:
        """
        Save a new profile for this user given a game/version.

        Parameters:
            userid - The user ID we are saving the profile for.
            profile - A dictionary that should be looked up later using get_profile.
        """
        await self.data.local.user.put_profile(self.game, self.version, userid, profile)

    async def update_play_statistics(self, userid: UserID, extra_stats: Optional[Dict[str, Any]] = None) -> None:
        """
        Given a user ID, calculate new play statistics.

        Handles keeping track of statistics such as consecutive days played, last
        play date, times played today, times played total, etc.

        Parameters:
            userid - The user ID we are binding the profile for.
        """

        # We store the play statistics in a series-wide settings blob so its available
        # across all game versions, since it isn't game-specific.
        settings = await self.get_play_statistics(userid)

        if extra_stats is not None:
            for key in extra_stats:
                # Make sure we don't override anything we manage here
                if key in [
                    'total_plays',
                    'today_plays',
                    'total_days',
                    'first_play_timestamp',
                    'last_play_timestamp',
                    'last_play_date',
                    'consecutive_days',
                ]:
                    continue
                # Safe to copy over
                settings[key] = extra_stats[key]

        settings.replace_int('total_plays', settings.get_int('total_plays') + 1)
        settings.replace_int('first_play_timestamp', settings.get_int('first_play_timestamp', int(Time.now())))
        settings.replace_int('last_play_timestamp', int(Time.now()))

        last_play_date = settings.get_int_array('last_play_date', 3)
        today_play_date = Time.todays_date()
        yesterday_play_date = Time.yesterdays_date()
        if (
                last_play_date[0] == today_play_date[0] and
                last_play_date[1] == today_play_date[1] and
                last_play_date[2] == today_play_date[2]
        ):
            # We already played today, add one
            settings.replace_int('today_plays', settings.get_int('today_plays') + 1)
        else:
            # We played on a new day, so count total days up
            settings.replace_int('total_days', settings.get_int('total_days') + 1)

            # We haven't played yet today, reset to one
            settings.replace_int('today_plays', 1)
            if (
                    last_play_date[0] == yesterday_play_date[0] and
                    last_play_date[1] == yesterday_play_date[1] and
                    last_play_date[2] == yesterday_play_date[2]
            ):
                # We played yesterday, add one to consecutive days
                settings.replace_int('consecutive_days', settings.get_int('consecutive_days') + 1)
            else:
                # We haven't played yet today or yesterday, reset consecutive days
                settings.replace_int('consecutive_days', 1)
        settings.replace_int_array('last_play_date', 3, today_play_date)

        # Save back
        await self.data.local.game.put_settings(self.game, userid, settings)

    async def get_machine_id(self) -> int:
        machine = await self.data.local.machine.get_machine(self.config['machine']['pcbid'])
        return machine.id

    async def update_machine_name(self, newname: Optional[str]) -> None:
        if newname is None:
            return
        machine = await self.data.local.machine.get_machine(self.config['machine']['pcbid'])
        machine.name = newname
        await self.data.local.machine.put_machine(machine)

    async def update_machine_data(self, newdata: Dict[str, Any]) -> None:
        machine = await self.data.local.machine.get_machine(self.config['machine']['pcbid'])
        machine.data.update(newdata)
        await self.data.local.machine.put_machine(machine)

    async def get_game_config(self) -> ValidatedDict:
        machine = await self.data.local.machine.get_machine(self.config['machine']['pcbid'])
        if machine.arcade is not None:
            settings = await self.data.local.machine.get_settings(machine.arcade, self.game, self.version, 'game_config')
        else:
            settings = None

        if settings is None:
            settings = ValidatedDict()
        return settings

    async def get_play_statistics(self, userid: UserID) -> ValidatedDict:
        """
        Given a user ID, get the play statistics.

        Note that games wishing to use this when generating profiles to send to
        a game should call update_play_statistics when parsing a profile save.

        Parameters:
            userid - The user ID we are binding the profile for.

        Returns a dictionary optionally containing the following attributes:
            total_plays - Integer count of total plays for this game series
            first_play_timestamp - Unix timestamp of first play time
            last_play_timestamp - Unix timestamp of last play time
            last_play_date - List of ints in the form of [YYYY, MM, DD] of last play date
            today_plays - Number of times played today
            total_days - Total individual days played
            consecutive_days - Number of consecutive days played at this time.
        """
        settings = await self.data.local.game.get_settings(self.game, userid)
        if settings is None:
            return ValidatedDict({})
        return settings
