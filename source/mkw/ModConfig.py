from pathlib import Path
from typing import Generator

from PIL import Image

from source import threaded
from source.mkw import Tag, Color
from source.mkw.Cup import Cup
from source.mkw.Track import Track
import json

from source.wt.szs import SZSPath

CT_ICON_SIZE: int = 128


Thread: any


# representation of the configuration of a mod


class ModConfig:
    __slots__ = ("name", "path", "nickname", "variant", "tags_prefix", "tags_suffix",
                 "default_track", "_tracks", "version", "original_track_prefix", "swap_original_order",
                 "keep_original_track", "enable_random_cup", "tags_cups", "track_file_template")

    def __init__(self, path: Path | str, name: str, nickname: str = None, version: str = None, variant: str = None,
                 tags_prefix: dict[Tag, Color] = None, tags_suffix: dict[Tag, Color] = None,
                 tags_cups: list[Tag] = None,
                 default_track: "Track | TrackGroup" = None, tracks: list["Track | TrackGroup"] = None,
                 original_track_prefix: bool = None, swap_original_order: bool = None,
                 keep_original_track: bool = None, enable_random_cup: bool = None,
                 track_file_template: str = None):

        self.path = Path(path)

        self.name: str = name
        self.nickname: str = nickname if nickname is not None else name
        self.version: str = version if version is not None else "v1.0.0"
        self.variant: str = variant if variant is not None else "01"

        self.tags_prefix: dict[Tag] = tags_prefix if tags_prefix is not None else {}
        self.tags_suffix: dict[Tag] = tags_suffix if tags_suffix is not None else {}
        self.tags_cups: list[Tag] = tags_cups if tags_cups is not None else []

        self.default_track: "Track | TrackGroup" = default_track if default_track is not None else None
        self._tracks: list["Track | TrackGroup"] = tracks if tracks is not None else []
        self.track_file_template: str = track_file_template \
            if track_file_template is not None else "{{ getattr(track, 'sha1', '_') }}"

        self.original_track_prefix: bool = original_track_prefix if original_track_prefix is not None else True
        self.swap_original_order: bool = swap_original_order if swap_original_order is not None else True
        self.keep_original_track: bool = keep_original_track if keep_original_track is not None else True
        self.enable_random_cup: bool = enable_random_cup if enable_random_cup is not None else True

    def __repr__(self):
        return f"<ModConfig name={self.name} version={self.version}>"

    @classmethod
    def from_dict(cls, path: Path | str, config_dict: dict) -> "ModConfig":
        """
        Create a ModConfig from a dict
        :param path: path of the mod_config.json
        :param config_dict: dict containing the configuration
        :return: ModConfig
        """
        kwargs = {
            attr: config_dict.get(attr)
            for attr in cls.__slots__
            if attr not in ["name", "default_track", "_tracks", "tracks", "path"]
            # these keys are treated after or are reserved
        }

        return cls(
            path=Path(path),
            name=config_dict["name"],

            **kwargs,

            default_track=Track.from_dict(config_dict.get("default_track", {})),
            tracks=[Track.from_dict(track) for track in config_dict.get("tracks", [])],
        )

    @classmethod
    def from_file(cls, config_file: str | Path) -> "ModConfig":
        """
        Create a ModConfig from a file
        :param config_file: file containing the configuration
        :return: ModConfig
        """
        config_file = Path(config_file)
        return cls.from_dict(
            path=config_file,
            config_dict=json.loads(config_file.read_text(encoding="utf8"))
        )

    def get_mod_directory(self) -> Path:
        """
        Get the directory of the mod
        :return: directory of the mod
        """
        return self.path.parent

    def get_tracks(self) -> Generator["Track", None, None]:
        """
        Get all the track elements
        :return: track elements
        """
        for track in self._tracks:
            yield from track.get_tracks()

    def get_ordered_cups(self) -> Generator["Cup", None, None]:
        """
        Get all the cups with cup tags
        :return: cups with cup tags
        """
        # use self._tracks instead of self._get_tracks() because we want the TrackGroup
        # for track that have a tag in self.tags_cups
        for tag_cup in self.tags_cups:
            track_buffer: "Track | TrackGroup" = []
            current_tag_name, current_tag_count = tag_cup, 0

            # every four 4 tracks, create a cup
            for track in filter(lambda track: tag_cup in getattr(track, "tags", []), self._tracks):
                track_buffer.append(track)

                if len(track_buffer) > 4:
                    current_tag_count += 1
                    yield Cup(tracks=track_buffer, cup_name=f"{current_tag_name}/{current_tag_count}")
                    track_buffer = []

            # if there is still tracks in the buffer, create a cup with them and fill with default>
            if len(track_buffer) > 0:
                track_buffer.extend([self.default_track] * (4 - len(track_buffer)))
                yield Cup(tracks=track_buffer, cup_name=f"{current_tag_name}/{current_tag_count+1}")

    def get_unordered_cups(self) -> Generator["Cup", None, None]:
        """
        Get all the cups with no cup tags
        :return: cups with no cup tags
        """
        # for track that have don't have a tag in self.tags_cups
        track_buffer: "Track | TrackGroup" = []
        for track in filter(
            lambda track: not any(item in getattr(track, "tags", []) for item in self.tags_cups),
            self._tracks
        ):
            track_buffer.append(track)

            if len(track_buffer) > 4:
                yield Cup(tracks=track_buffer)
                track_buffer = []

        # if there is still tracks in the buffer, create a cup with them and fill with default
        if len(track_buffer) > 0:
            track_buffer.extend([self.default_track] * (4 - len(track_buffer)))
            yield Cup(tracks=track_buffer)

    def get_cups(self) -> Generator["Cup", None, None]:
        """
        Get all the cups
        :return: cups
        """
        yield from self.get_ordered_cups()
        yield from self.get_unordered_cups()

    def get_ctfile(self) -> str:
        """
        Return the ct_file generated from the ModConfig
        :return: ctfile content
        """
        lecode_flags = filter(lambda v: v is not None, [
            "N$SHOW" if self.keep_original_track else "N$NONE",
            "N$F_WII" if self.original_track_prefix else None,
            "N$SWAP" if self.swap_original_order else None
        ])

        ctfile = (
            f"#CT-CODE\n"  # magic number
            f"[RACING-TRACK-LIST]\n"  # start of the track section
            f"%LE-FLAGS=1\n"  # enable lecode mode
            f"%WIIMM-CUP={int(self.enable_random_cup)}\n"  # enable random cup
            f"N {' | '.join(lecode_flags)}\n"  # other flags to disable default tracks, ...
            f"\n"
        )

        for cup in self.get_cups():
            # get all the cup ctfile, use "-" for the template since the track's name are not used here
            ctfile += cup.get_ctfile(mod_config=self, template="-")

        return ctfile

    def get_base_cticons(self) -> Generator[Image.Image, None, None]:
        """
        Return the base cticon
        :return:
        """
        icon_names = ["left", "right"]

        if self.keep_original_track:
            icon_names += [
                f"_DEFAULT/{name}"
                for name in (
                    ["mushroom", "shell", "flower", "banana", "star", "leaf", "special", "lightning"]
                    if self.swap_original_order else
                    ["mushroom", "flower", "star", "special", "shell", "banana", "leaf", "lightning"]
                )
            ]
        if self.enable_random_cup: icon_names.append("random")

        for icon_name in icon_names:
            yield Image.open(self.get_mod_directory() / f"_CUPS/{icon_name}.png").resize((CT_ICON_SIZE, CT_ICON_SIZE))

    def get_custom_cticons(self) -> Generator[Image.Image, None, None]:
        """
        Return the custom ct_icon generated from the ModConfig
        :return:
        """
        for cup in self.get_cups():
            yield cup.get_cticon(mod_config=self).resize((CT_ICON_SIZE, CT_ICON_SIZE))

    def get_cticons(self) -> Generator[Image.Image, None, None]:
        """
        Return all the ct_icon generated from the ModConfig
        :return:
        """
        yield from self.get_base_cticons()
        yield from self.get_custom_cticons()

    @staticmethod
    def get_default_font() -> Path:
        """
        Return the default font for creating ct_icons
        :return: the path to the default font file
        """
        return Path("./assets/SuperMario256.ttf")

    def get_full_cticon(self) -> Image.Image:
        """
        Return the full ct_icon generated from the ModConfig
        :return:
        """
        cticons = list(self.get_cticons())

        full_cticon = Image.new("RGBA", (CT_ICON_SIZE, CT_ICON_SIZE * len(cticons)))
        for i, cticon in enumerate(cticons): full_cticon.paste(cticon, (0, i * CT_ICON_SIZE))

        return full_cticon

    def normalize_all_tracks(self, autoadd_path: "Path | str", destination_path: "Path | str",
                             thread_amount: int = 8) -> Generator[dict, None, None]:
        """
        Convert all tracks of the mod to szs into the destination_path
        :param thread_amount: number of thread to use
        :param autoadd_path: autoadd directory
        :param destination_path: destination where the files are converted
        """
        yield {"description": "Normalizing track..."}
        destination_path = Path(destination_path)
        destination_path.mkdir(parents=True, exist_ok=True)

        normalize_threads: list[dict] = []

        def remove_finished_threads() -> Generator[dict, None, None]:
            """
            Remove all the thread that stopped in a thread list
            :return: the list without the stopped thread
            """
            nonlocal normalize_threads

            yield {"description": f"Normalizing tracks :\n" + "\n".join(thread['name'] for thread in normalize_threads)}
            normalize_threads = list(filter(lambda thread: thread["thread"].is_alive(), normalize_threads))

        # for every track in the tracks mod directory, convert it to szs (in a threaded way)
        for track_file in filter(lambda file: file.is_file(), (self.path.parent / "_TRACKS").rglob("*")):
            @threaded
            def normalize_track():
                SZSPath(track_file).normalize(
                    autoadd_path,
                    destination_path / track_file.with_suffix(".szs").name,
                    format="szs"
                )

            normalize_threads.append({"name": track_file.name, "thread": normalize_track()})
            while len(normalize_threads) > thread_amount: yield from remove_finished_threads()
            # if there is more than the max amount of thread running, wait for one to finish
        while len(normalize_threads) > 0: yield from remove_finished_threads()
        # if there is no longer any track to add, wait for all process to finish
