from .Track import Track


class Cup:
    def __init__(self, name: str = None,
                 track1: Track = None,
                 track2: Track = None,
                 track3: Track = None,
                 track4: Track = None,
                 locked: bool = False,
                 *args, **kwargs):
        """
        class of a cup
        :param name: name of the cup
        :param track1: first track
        :param track2: second track
        :param track3: third track
        :param track4: fourth track
        :param locked: is the track locked (used to load ctconfig in CT_Config)
        :param args: other args that I could add in the future
        :param kwargs: other kwargs that I could add in the future
        """

        self.name = name
        self.locked = locked
        self.tracks = [
            track1 if track1 else Track(),
            track2 if track2 else Track(),
            track3 if track3 else Track(),
            track4 if track4 else Track()
        ]

    def get_ctfile_cup(self, *args, **kwargs) -> str:
        """
        get the ctfile definition for the cup
        :param race: is it a text used for Race_*.szs ?
        :return: ctfile definition for the cup
        """
        ctfile_cup = f'\nC "{self.name}"\n'
        for track in self.tracks:
            ctfile_cup += track.get_ctfile(*args, **kwargs)
        return ctfile_cup

    def load_from_json(self, cup: dict) -> None:
        """
        load the cup from a dictionnary
        :param cup: dictionnary cup
        """
        for key, value in cup.items():  # load all value in the json as class attribute
            if key == "tracks":  # if the key is tracks
                for i, track_json in enumerate(value):  # load all tracks from their json
                    self.tracks[int(i)].load_from_json(track_json)
            else:
                setattr(self, key, value)
