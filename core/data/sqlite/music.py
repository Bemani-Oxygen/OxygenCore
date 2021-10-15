from sqlalchemy import Table, Column, UniqueConstraint  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
from sqlalchemy.types import String, Integer, JSON  # type: ignore
from sqlalchemy.dialects.mysql import BIGINT as BigInteger  # type: ignore
from typing import Optional, Dict, List, Tuple, Any

from ...common import Time
from ..exceptions import ScoreSaveException
from .base import BaseData, metadata
from ..types import Score, Attempt, Song, UserID

"""
Table for storing a score for a particular game. This is keyed by userid and
musicid, as a user can only have one score for a particular song/chart combo.
This has a JSON blob for any data the game wishes to store, such as points, medals,
ghost, etc.

Note that this is NOT keyed by game song id and chart, but by an internal musicid
managed by the music table. This is so we can support keeping the same score across
multiple games, even if the game changes the ID it refers to the song by.
"""
score = Table(
    'score',
    metadata,
    Column('id', Integer, nullable=False, primary_key=True),
    Column('userid', BigInteger(unsigned=True), nullable=False),
    Column('game', String(32), nullable=False),
    Column('musicid', Integer, nullable=False, index=True),
    Column('points', Integer, nullable=False, index=True),
    Column('timestamp', Integer, nullable=False, index=True),
    Column('update', Integer, nullable=False, index=True),
    Column('lid', Integer, nullable=False, index=True),
    Column('data', JSON, nullable=False),
    UniqueConstraint('userid', 'musicid', name='userid_musicid'),
    mysql_charset='utf8mb4',
)

"""
Table for storing score history for a particular game. Every entry that is stored
or updated in score will be written into this table as well, for looking up history
over time.
"""
score_history = Table(
    'score_history',
    metadata,
    Column('id', Integer, nullable=False, primary_key=True),
    Column('userid', BigInteger(unsigned=True), nullable=False),
    Column('game', String(32), nullable=False),
    Column('musicid', Integer, nullable=False, index=True),
    Column('points', Integer, nullable=False),
    Column('timestamp', Integer, nullable=False, index=True),
    Column('lid', Integer, nullable=False, index=True),
    Column('new_record', Integer, nullable=False),
    Column('data', JSON, nullable=False),
    UniqueConstraint('userid', 'musicid', 'timestamp', name='userid_musicid_timestamp'),
    mysql_charset='utf8mb4',
)


class MusicData(BaseData):

    def __get_musicid(self, game: str, version: int, songid: int, songchart: int) -> int:
        """
        Given a game/version/songid/chart, look up the unique music ID for this song.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            songid - ID of the song according to the game.
            songchart - Chart number according to the game.

        Returns:
            Integer representing music ID if found or raises an exception otherwise.
        """
        return songid * 10000 + version * 100 + songchart

    def __get_songid(self, musicid: int) -> int:
        """
        Given a musicid, look up the unique song ID for this song.

        Parameters:
            musicid - Mixed game/version/songid/chart by self.__get_musicid.

        Returns:
            Integer representing song ID if found or raises an exception otherwise.
        """
        return int(musicid / 10000)

    def __get_songchart(self, musicid: int) -> int:
        """
        Given a musicid, look up the chart for this song.

        Parameters:
            musicid - Mixed game/version/songid/chart by self.__get_musicid.

        Returns:
            Integer representing song ID if found or raises an exception otherwise.
        """
        return int(musicid % 100)

    async def put_score(
            self,
            game: str,
            version: int,
            userid: UserID,
            songid: int,
            songchart: int,
            location: int,
            points: int,
            data: Dict[str, Any],
            new_record: bool,
            timestamp: Optional[int] = None,
    ) -> None:
        """
        Given a game/version/song/chart and user ID, save a new/updated high score.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.
            songid - ID of the song according to the game.
            songchart - Chart number according to the game.
            location - Machine ID where this score was earned.
            points - Points obtained on this song.
            data - Data that the game wishes to record along with the score.
            new_record - Whether this score was a new record or not.
            timestamp - Optional integer specifying when the high score happened.
        """
        # First look up the song/chart from the music DB
        musicid = self.__get_musicid(game, version, songid, songchart)
        ts = timestamp if timestamp is not None else Time.now()

        # Add to user score
        if new_record:
            # We want to update the timestamp/location to now if its a new record.
            sql = (
                    "INSERT INTO `score` (`userid`, `game`, `musicid`, `points`, `data`, `timestamp`, `update`, `lid`) " +
                    "VALUES (:userid, :game, :musicid, :points, :data, :timestamp, :update, :location) " +
                    "ON CONFLICT(userid, musicid) DO UPDATE SET data=excluded.data, points = excluded.points, " +
                    "timestamp = excluded.timestamp, `update` = excluded.'update', lid = excluded.lid"
            )
        else:
            # We only want to add the timestamp if it is new.
            sql = (
                    "INSERT INTO `score` (`userid`, `game`, `musicid`, `points`, `data`, `timestamp`, `update`, `lid`) " +
                    "VALUES (:userid, :game, :musicid, :points, :data, :timestamp, :update, :location) " +
                    "ON CONFLICT(userid, musicid) DO UPDATE SET data=excluded.data, points = excluded.points, `update` = excluded.'update'"
            )
        await self.execute(
            sql,
            {
                'userid': userid,
                'game': game,
                'musicid': musicid,
                'points': points,
                'data': self.serialize(data),
                'timestamp': ts,
                'update': ts,
                'location': location,
            }
        )

    async def put_attempt(
            self,
            game: str,
            version: int,
            userid: Optional[UserID],
            songid: int,
            songchart: int,
            location: int,
            points: int,
            data: Dict[str, Any],
            new_record: bool,
            timestamp: Optional[int] = None,
    ) -> None:
        """
        Given a game/version/song/chart and user ID, save a single score attempt.

        Note that this is different than put_score above, because a user may have only one score
        per song/chart in a given game, but they can have as many history entries as times played.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.
            songid - ID of the song according to the game.
            songchart - Chart number according to the game.
            location - Machine ID where this score was earned.
            points - Points obtained on this song.
            data - Optional data that the game wishes to record along with the score.
            new_record - Whether this score was a new record or not.
            timestamp - Optional integer specifying when the attempt happened.
        """
        # First look up the song/chart from the music DB
        musicid = self.__get_musicid(game, version, songid, songchart)
        ts = timestamp if timestamp is not None else Time.now()

        # Add to score history
        sql = (
                "INSERT INTO `score_history` (userid, game, musicid, timestamp, lid, new_record, points, data) " +
                "VALUES (:userid, :game, :musicid, :timestamp, :location, :new_record, :points, :data)"
        )
        try:
            await self.execute(
                sql,
                {
                    'userid': userid if userid is not None else 0,
                    'game': game,
                    'musicid': musicid,
                    'timestamp': ts,
                    'location': location,
                    'new_record': 1 if new_record else 0,
                    'points': points,
                    'data': self.serialize(data),
                },
            )
        except IntegrityError:
            raise ScoreSaveException(
                f'There is already an attempt by {userid if userid is not None else 0} for music id {musicid} at {ts}'
            )

    async def get_score(self, game: str, version: int, userid: UserID, songid: int, songchart: int) -> Optional[Score]:
        """
        Look up a user's previous high score.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.
            songid - ID of the song according to the game.
            songchart - Chart number according to the game.

        Returns:
            The optional data stored by the game previously, or None if no score exists.
        """
        musicid = self.__get_musicid(game, version, songid, songchart)
        sql = (
                "SELECT score.id AS scorekey, score.timestamp AS timestamp, 'score.update' AS 'update', score.lid AS lid, " +
                "(select COUNT(score_history.timestamp) FROM score_history WHERE score_history.musicid = :musicid AND score_history.userid = :userid AND score_history.game = :game) AS plays, " +
                "score.points AS points, score.data AS data FROM score WHERE score.userid = :userid AND score.musicid = :musicid AND score.game = :game"
        )
        cursor = await self.execute(
            sql,
            {
                'userid': userid,
                'game': game,
                'musicid': musicid,
            },
        )

        result = cursor.fetchone()

        if result is None:
            # score doesn't exist
            return None

        return Score(
            result['scorekey'],
            songid,
            songchart,
            result['points'],
            result['timestamp'],
            result['update'],
            result['lid'],
            result['plays'],
            self.deserialize(result['data']),
        )

    async def get_scores(
        self,
        game: str,
        version: int,
        userid: UserID,
        since: Optional[int]=None,
        until: Optional[int]=None,
    ) -> List[Score]:
        """
        Look up all of a user's previous high scores.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.

        Returns:
            A list of Score objects representing all high scores for a game.
        """
        sql = (
            "SELECT score.musicid AS musicid, score.id AS scorekey, score.timestamp AS timestamp, 'score.update' AS `update`, score.lid AS lid, " +
            "(select COUNT(score_history.timestamp) FROM score_history WHERE score_history.musicid = score.musicid AND score_history.userid = :userid AND score_history.game = :game) AS plays, " +
            "score.points AS points, score.data AS data FROM score WHERE score.userid = :userid AND score.game = :game"
        )
        if since is not None:
            sql = sql + ' AND score.update >= :since'
        if until is not None:
            sql = sql + ' AND score.update < :until'
        cursor = await self.execute(sql, {'userid': userid, 'game': game, 'version': version, 'since': since, 'until': until})

        scores = []
        for result in cursor.fetchall():
            songid = self.__get_songid(result['musicid'])
            songchart = self.__get_songchart(result['musicid'])
            scores.append(
                Score(
                    result['scorekey'],
                    songid,
                    songchart,
                    result['points'],
                    result['timestamp'],
                    result['update'],
                    result['lid'],
                    result['plays'],
                    self.deserialize(result['data']),
                )
            )

        return scores

    async def get_most_played(self, game: str, version: int, userid: UserID, count: int) -> List[Tuple[int, int]]:
        """
        Look up a user's most played songs.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.
            count - Number of scores to look up.

        Returns:
            A list of tuples, containing the songid and the number of plays across all charts for that song.
        """
        sql = (
                "SELECT score_history.musicid AS musicid, COUNT(score_history.timestamp) AS plays FROM score_history " +
                "WHERE score_history.userid = :userid AND score_history.game = :game " +
                "GROUP BY musicid ORDER BY plays DESC LIMIT :count"
        )
        cursor = await self.execute(sql, {'userid': userid, 'game': game, 'version': version, 'count': count})

        most_played = []
        for result in cursor.fetchall():
            songid = self.__get_songid(result['musicid'])
            most_played.append(
                (songid, result['plays'])
            )

        return most_played

    async def get_last_played(self, game: str, version: int, userid: UserID, count: int) -> List[Tuple[int, int]]:
        """
        Look up a user's last played songs.

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            userid - Integer representing a user. Usually looked up with UserData.
            count - Number of scores to look up.

        Returns:
            A list of tuples, containing the songid and the last played time for this song.
        """
        sql = (
                "SELECT DISTINCT(score_history.musicid) AS musicid, score_history.timestamp AS timestamp FROM score_history " +
                "WHERE score_history.userid = :userid AND score_history.game = :game " +
                "ORDER BY timestamp DESC LIMIT :count"
        )
        cursor = await self.execute(sql, {'userid': userid, 'game': game, 'version': version, 'count': count})

        last_played = []
        for result in cursor.fetchall():
            songid = self.__get_songid(result['musicid'])
            last_played.append(
                (songid, result['timestamp'])
            )

        return last_played

    async def get_attempt_by_key(self, game: str, version: int, key: int) -> Optional[Tuple[UserID, Attempt]]:
        """
        Look up a previous attempt by key.
        TODO

        Parameters:
            game - String representing a game series.
            version - Integer representing which version of the game.
            key - Integer representing a unique key fetched in a previous Attempt lookup.

        Returns:
            The optional data stored by the game previously, or None if no score exists.
        """
        sql = (
                "SELECT music.songid AS songid, music.chart AS chart, score_history.id AS scorekey, score_history.timestamp AS timestamp, score_history.userid AS userid, " +
                "score_history.lid AS lid, score_history.new_record AS new_record, score_history.points AS points, score_history.data AS data FROM score_history, music " +
                "WHERE score_history.id = :scorekey AND score_history.musicid = music.id AND music.game = :game AND music.version = :version"
        )
        cursor = await self.execute(
            sql,
            {
                'game': game,
                'version': version,
                'scorekey': key,
            },
        )

        result = cursor.fetchone()

        if result is None:
            # score doesn't exist
            return None

        return (
            UserID(result['userid']),
            Attempt(
                result['scorekey'],
                result['songid'],
                result['chart'],
                result['points'],
                result['timestamp'],
                result['lid'],
                True if result['new_record'] == 1 else False,
                self.deserialize(result['data']),
            )
        )