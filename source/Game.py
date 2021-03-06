from PIL import Image, ImageDraw, ImageFont
import shutil
import glob

from source.definition import *
from source.wszst import *
from source.Error import *
from source.Track import Track


class Game:
    def __init__(self, common, path: str = "", region_ID: str = "P", game_ID: str = "RMCP01"):
        """
        Class about the game code and its treatment.
        :param path: path of the game file / directory
        :param region_ID: game's region id (P for PAL, K for KOR, ...)
        :param game_ID: game's id (RMCP01 for PAL, ...)
        :param common: common class to access all other element
        """
        if not os.path.exists(path) and path: raise InvalidGamePath()
        self.extension = None
        self.path = path
        self.set_path(path)
        self.region = region_id_to_name[region_ID]
        self.region_ID = region_ID
        self.game_ID = game_ID
        self.common = common

    def set_path(self, path: str) -> None:
        """
        Change game path
        :param path: game's file
        """
        self.extension = get_extension(path).upper()
        self.path = path

    def convert_to(self, format: str = "FST") -> None:
        """
        Convert game to an another format
        :param format: game format (ISO, WBFS, ...)
        """
        if format in ["ISO", "WBFS", "CISO"]:
            path_game_format: str = os.path.realpath(self.path + f"/../{self.common.ct_config.nickname} v{self.common.ct_config.version}." + format.lower())
            wit.copy(src_path=self.path, dst_path=path_game_format, format=format)
            shutil.rmtree(self.path)
            self.path = path_game_format

            self.common.gui_main.progress(statut=self.common.translate("Changing game's ID"), add=1)
            wit.edit(
                file=self.path,
                region_ID=self.region_ID,
                game_variant=self.common.ct_config.game_variant,
                name=f"{self.common.ct_config.name} {self.common.ct_config.version}"
            )

    def extract(self) -> None:
        """
        Extract game file in the same directory.
        """
        if self.extension == "DOL":
            self.path = os.path.realpath(self.path + "/../../")  # main.dol is in PATH/sys/, so go back 2 dir upper

        elif self.extension in ["ISO", "WBFS", "CSIO"]:
            # Fiding a directory name that doesn't already exist
            path_dir = get_next_available_dir(
                parent_dir=self.path + f"/../",
                dir_name=f"{self.common.ct_config.nickname} v{self.common.ct_config.version}"
            )

            wit.extract(file=self.path, dst_dir=path_dir)

            self.path = path_dir
            if os.path.exists(self.path + "/DATA"): self.path += "/DATA"
            self.extension = "DOL"

        else:
            raise InvalidFormat()

        if glob.glob(self.path + "/files/rel/lecode-???.bin"):  # if a LECODE file is already here
            raise RomAlreadyPatched()  # warning already patched

        if os.path.exists(self.path + "/setup.txt"):
            with open(self.path + "/setup.txt") as f: setup = f.read()
            setup = setup[setup.find("!part-id = ") + len("!part-id = "):]
            self.game_ID = setup[:setup.find("\n")]

            self.region_ID = self.game_ID[3]
            self.region = region_id_to_name[self.region_ID] if self.region_ID in region_id_to_name else self.region

    def count_patch_subfile_operation(self) -> int:
        """
        count all the step patching subfile will take (for the progress bar)
        :return: number of step estimated
        """

        # This part is used to estimate the max_step
        extracted_file = []
        max_step = 1

        def count_rf(path):
            nonlocal max_step
            max_step += 1
            if get_extension(path) == "szs":
                if not (os.path.realpath(path) in extracted_file):
                    extracted_file.append(os.path.realpath(path))
                    max_step += 1

        fs = self.common.ct_config.file_structure
        for fp in fs:
            for f in glob.glob(self.path + "/files/" + fp, recursive=True):
                if type(fs[fp]) == str:
                    count_rf(path=f)
                elif type(fs[fp]) == dict:
                    for nf in fs[fp]:
                        if type(fs[fp][nf]) == str:
                            count_rf(path=f)
                        elif type(fs[fp][nf]) == list:
                            for ffp in fs[fp][nf]: count_rf(path=f)

        return max_step

    def install_patch_subfile(self) -> None:
        """
        patch subfile as indicated in the file_structure.json file (for file structure)
        """

        extracted_file = []
        self.common.gui_main.progress(show=True, indeter=False, statut=self.common.translate("Modifying subfile..."), add=1)

        def replace_file(path, file, subpath="/") -> None:
            """
            Replace subfile in the .szs file
            :param path: path to the .szs file
            :param file: file to replace
            :param subpath: directory between .szs file and file inside to replace
            """
            self.common.gui_main.progress(statut=self.common.translate("Editing", "\n", get_nodir(path)), add=1)
            extension = get_extension(path)

            source_file = f"{self.common.ct_config.pack_path}/file/{file}"
            dest_file = path

            if extension == "szs":
                if os.path.realpath(path) not in extracted_file:
                    szs.extract(file=path)
                    extracted_file.append(os.path.realpath(path))

                szs_extract_path = path + ".d"
                if os.path.exists(szs_extract_path + subpath):
                    dest_file = szs_extract_path + subpath
                    if subpath[-1] == "/": dest_file += get_nodir(file)

            elif path[-1] == "/": dest_file += get_nodir(file)

            shutil.copyfile(source_file, dest_file)

        fs = self.common.ct_config.file_structure
        for fp in fs:
            for f in glob.glob(self.path + "/files/" + fp, recursive=True):
                if type(fs[fp]) == str:
                    replace_file(path=f, file=fs[fp])
                elif type(fs[fp]) == dict:
                    for nf in fs[fp]:
                        if type(fs[fp][nf]) == str:
                            replace_file(path=f, subpath=nf, file=fs[fp][nf])
                        elif type(fs[fp][nf]) == list:
                            for ffp in fs[fp][nf]: replace_file(path=f, subpath=nf, file=ffp)

        for file in extracted_file:
            self.common.gui_main.progress(statut=self.common.translate("Recompilating", "\n", get_nodir(file)), add=1)
            szs.create(file=file)
            shutil.rmtree(file + ".d", ignore_errors=True)

    def install_copy_mystuff(self) -> None:
        """
        copy MyStuff directory into the game *before* patching the game
        """
        self.common.gui_main.progress(show=True, indeter=False, statut=self.common.translate("Copying MyStuff..."), add=1)

        mystuff_folder = self.common.gui_main.stringvar_mystuff_folder.get()
        if mystuff_folder and mystuff_folder != "None":

            # replace game's file by files with the same name in the MyStuff root
            mystuff_files = {}
            for mystuff_file in glob.glob(f"{mystuff_folder}/*"):   # for every file at the root of the mystuff folder
                basename = os.path.basename(mystuff_file)

                if os.path.isfile(mystuff_file):
                    #  replace the game files with the file at mystuff's root
                    mystuff_files[basename] = mystuff_file
                else:
                    #  if this is a dict, simply copy it into the game files
                    shutil.copytree(mystuff_file, f"{self.path}/files/{basename}/", dirs_exist_ok=True)

            for game_file in glob.glob(f"{self.path}/files/**/*", recursive=True):
                basename = os.path.basename(game_file)
                if basename in mystuff_files:
                    mystuff_file = mystuff_files[basename]
                    shutil.copy(mystuff_file, game_file)
                    print(f"copied {mystuff_file} to {game_file}")

    def install_patch_maindol(self) -> None:
        """
        patch the main.dol file to allow the addition of LECODE.bin file
        """
        self.common.gui_main.progress(statut=self.common.translate("Patch main.dol"), add=1)

        region_id = self.common.ct_config.region if self.common.gui_main.is_using_official_config() else self.common.ct_config.cheat_region
        wstrt.patch(path=self.path, region_id=region_id)

    def install_patch_lecode(self) -> None:
        """
        configure and add the LECODE.bin file to the mod
        """
        self.common.gui_main.progress(statut=self.common.translate("Patch lecode.bin"), add=1)

        fileprocess_placement = self.common.ct_config.file_process.get("placement", {})

        lpar_path = fileprocess_placement.get("lpar_dir", "")
        lpar_path = (
            f"{self.common.ct_config.pack_path}/file/{lpar_path}/"
            f"lpar-{'debug' if self.common.gui_main.boolvar_use_debug_mode.get() else 'normal'}.txt"
        )

        lecode_file = fileprocess_placement.get("lecode_bin_dir", "")
        lecode_file = f"{self.common.ct_config.pack_path}/file/{lecode_file}/lecode-{self.region}.bin"

        lec.patch(
            lecode_file=lecode_file,
            dest_lecode_file=f"{self.path}/files/rel/lecode-{self.region}.bin",
            game_track_path=f"{self.path}/files/Race/Course/",
            copy_track_paths=[f"./file/Track/"],
            move_track_paths=[f"{self.path}/files/Race/Course/"],
            ctfile_path="./file/CTFILE.txt",
            lpar_path=lpar_path,
        )

    def install_convert_rom(self) -> None:
        """
        convert the rom to the selected game format
        """
        output_format = self.common.gui_main.stringvar_game_format.get()
        self.common.gui_main.progress(statut=self.common.translate("Converting to", " ", output_format), add=1)
        self.convert_to(output_format)

    def install_mod(self) -> None:
        """
        Patch the game to install the mod
        """
        try:
            max_step = 5 + self.count_patch_subfile_operation()
            # PATCH main.dol and PATCH lecode.bin, converting, changing ID, copying MyStuff Folder

            self.common.gui_main.progress(statut=self.common.translate("Installing mod..."), max=max_step, step=0)
            self.install_copy_mystuff()
            self.install_patch_subfile()
            self.install_patch_maindol()
            self.install_patch_lecode()
            self.install_convert_rom()

            messagebox.showinfo(self.common.translate("End"), self.common.translate("The mod have been installed !"))

        except Exception as e:
            self.common.log_error()
            raise e

        finally:
            self.common.gui_main.progress(show=False)
            self.common.gui_main.quit()

    def patch_autoadd(self, auto_add_dir: str = "./file/auto-add") -> None:
        """
        Create the autoadd directory used to convert wbz track into szs
        :param auto_add_dir: autoadd directory
        """
        if os.path.exists(auto_add_dir): shutil.rmtree(auto_add_dir)
        szs.autoadd(path=self.path, dest_dir=auto_add_dir)

    def create_extra_common(self, bmgtracks: str, extra_common_path: str = "./file/ExtraCommon.txt") -> None:
        """
        this function create an "extra common" file : it contain modification about the original tracks name
        (the color modification) and allow the modification to be applied by overwritting the normal common
        file by this one.
        :param bmgtracks: bmg containing the track list
        :param extra_common_path: destination path to the extra common file
        """

        with open(extra_common_path, "w", encoding="utf8") as f:
            f.write("#BMG\n")

            for bmgtrack in bmgtracks.split("\n"):
                if "=" in bmgtrack:

                    prefix = ""
                    track_name = bmgtrack[bmgtrack.find("= ") + 2:]

                    if "T" in bmgtrack[:bmgtrack.find("=")]:
                        if not self.common.ct_config.keep_original_track: continue

                        start_track_id: int = bmgtrack.find("T")  # index where the bmg track definition start
                        track_id = bmgtrack[start_track_id:start_track_id + 3]
                        if track_id[1] in "1234":  # if the track is a original track from the wii
                            prefix = "Wii"
                            if prefix in Track.tags_color:
                                prefix = "\\\\c{" + Track.tags_color[prefix] + "}" + prefix + "\\\\c{off}"
                            prefix += " "

                        elif track_id[1] in "5678":  # if the track is a retro track from the original game
                            prefix, *track_name = track_name.split(" ")
                            track_name = " ".join(track_name)
                            if prefix in Track.tags_color:
                                prefix = "\\\\c{" + Track.tags_color[prefix] + "}" + prefix + "\\\\c{off}"
                            prefix += " "

                        track_id = hex(bmgID_track_move[track_id])[2:]

                    else:  # Arena
                        start_track_id: int = bmgtrack.find("U")  # index where the bmg arena definition start
                        track_id = bmgtrack[start_track_id:start_track_id + 3]

                        if track_id[1] == "2":  # if this is the retro cup of arenas
                            prefix, *track_name = track_name.split(" ")
                            track_name = " ".join(track_name)

                            if prefix in Track.tags_color:
                                prefix = "\\\\c{" + Track.tags_color[prefix] + "}" + prefix + "\\\\c{off}"
                            prefix += " "

                    if not self.common.ct_config.add_original_track_prefix: prefix = ""
                    f.write(f"  {track_id}\t= {prefix}{track_name}\n")

            if not self.common.ct_config.keep_original_track:
                for cup_index, cup in enumerate(self.common.ct_config.get_all_cups(), start=1):
                    if cup_index > 8: break  # only keep the 8 first cup
                    for track_index, track in enumerate(cup.get_tracks(), start=1):
                        f.write(
                            f"  T{cup_index}{track_index}\t= "
                            f"{track.get_track_formatted_name(filter_highlight=self.common.ct_config.filter_track_highlight)}"
                            f"\n"
                        )

            for arena in self.common.ct_config.arenas:
                f.write(
                    f"  U{arena.special[1:]}\t= "
                    f"{arena.get_track_formatted_name(filter_highlight=self.common.ct_config.filter_track_highlight)}"
                    f"\n"
                )

    def patch_bmg(self, gamefile: str) -> None:
        """
        Patch bmg file (text file)
        :param gamefile: an .szs file where file will be patched
        """

        bmg_replacement = {
            "MOD_NAME": self.common.ct_config.name,
            "MOD_NICKNAME": self.common.ct_config.nickname,
            "MOD_VERSION": self.common.ct_config.version,
            "MOD_CUSTOMIZED": "" if self.common.gui_main.is_using_official_config() else "(custom)",
            "ONLINE_SERVICE": "Wiimmfi",
        }

        bmglang = gamefile[-len("E.txt"):-len(".txt")]  # Langue du fichier
        self.common.gui_main.progress(statut=self.common.translate("Patching text", " ", bmglang), add=1)

        szs.extract(file=gamefile)

        bmgmenu = bmg.cat(path=gamefile, subfile=".d/message/Menu.bmg")  # Menu.bmg

        trackheader = "#--- standard track names"
        trackend = "2328"
        bmgtracks = bmg.cat(path=gamefile, subfile=".d/message/Common.bmg")  # Common.bmg
        bmgtracks = bmgtracks[bmgtracks.find(trackheader) + len(trackheader):bmgtracks.find(trackend)]

        self.create_extra_common(bmgtracks=bmgtracks, extra_common_path="./file/ExtraCommon.txt")

        bmgcommon = ctc.patch_bmg(ctfile="./file/CTFILE.txt",
                                  bmgs=[gamefile + ".d/message/Common.bmg", "./file/ExtraCommon.txt"])
        rbmgcommon = ctc.patch_bmg(ctfile="./file/RCTFILE.txt",
                                   bmgs=[gamefile + ".d/message/Common.bmg", "./file/ExtraCommon.txt"])

        shutil.rmtree(gamefile + ".d")

        def process_bmg_replacement(bmg_content: str, bmg_language: str) -> str:
            """
            This function apply the file_process to the bmg file. This allow text modification useful to
            change menu text (Wiimmfi for example) and the Wiimm's cup.
            :param bmg_content: content of the bmg to process
            :param bmg_language: language of the bmg file
            :return: the replaced bmg file
            """

            for bmg_process in self.common.ct_config.file_process.get("bmg", []):
                if "language" in bmg_process and bmg_language not in bmg_process["language"]:
                    continue

                for data, data_replacement in bmg_process["data"].items():
                    for key, replacement in bmg_replacement.items():
                        data_replacement = data_replacement.replace("{"+key+"}", replacement)

                    if bmg_process["mode"] == "overwrite_id":
                        start_line = f"\n\t{data} = "
                        start_pos = bmg_content.find(start_line)
                        if start_pos != -1:
                            end_pos = bmg_content[start_pos:].find("\n")
                            bmg_content = (
                                bmg_content[:start_pos] +
                                start_line + data_replacement +
                                bmg_content[end_pos:]
                            )
                        else:
                            bmg_content = f"{bmg_content}\n{start_line}{data_replacement}\n"

                    elif bmg_process["mode"] == "replace_text":
                        bmg_content = bmg_content.replace(data, data_replacement)

            return bmg_content

        def save_bmg(file: str, bmg_content: str) -> None:
            """
            Save and encode the bmg
            :param file: name of the bmg-text to save
            :param bmg_content: content to save in the bmg-text
            """
            with open(file, "w", encoding="utf-8") as f: f.write(bmg_content)
            bmg.encode(file)
            os.remove(file)

        fileprocess_placement = self.common.ct_config.file_process.get("placement", {})
        bmg_dir = fileprocess_placement.get("bmg_patch_dir", "")
        bmg_dir = f"{self.common.ct_config.pack_path}/file/{bmg_dir}"
        os.makedirs(get_dir(bmg_dir), exist_ok=True)

        save_bmg(f"{bmg_dir}/Menu_{bmglang}.txt", process_bmg_replacement(bmgmenu, bmglang))
        save_bmg(f"{bmg_dir}/Common_{bmglang}.txt", process_bmg_replacement(bmgcommon, bmglang))
        save_bmg(f"{bmg_dir}/Common_R{bmglang}.txt", process_bmg_replacement(rbmgcommon, bmglang))

    def patch_all_bmg(self) -> None:
        for file in glob.glob(f"{self.path}/files/Scene/UI/MenuSingle_?.szs"):
            self.patch_bmg(file)

    def patch_file(self):
        """
        Prepare all files to install the mod (track, bmg text, descriptive image, ...)
        """
        try:
            os.makedirs(f"./file/", exist_ok=True)
            os.makedirs(f"{self.common.ct_config.pack_path}/file/Track-WU8/", exist_ok=True)

            max_step = (
                len(self.common.ct_config.file_process.get("img_encode", {})) +
                self.common.ct_config.get_tracks_count() +
                3 +
                len("EGFIS")
            )

            self.common.gui_main.progress(
                show=True,
                indeter=False,
                statut=self.common.translate("Converting files"),
                max=max_step, step=0
            )
            self.common.gui_main.progress(statut=self.common.translate("Configurating LE-CODE"), add=1)
            self.common.ct_config.create_ctfile()

            self.generate_cticons()
            self.generate_all_image()
            self.patch_image()
            self.patch_all_bmg()
            self.patch_autoadd()
            self.patch_tracks()

        except Exception as e:
            self.common.log_error()
            raise e

        finally:
            self.common.gui_main.progress(show=False)

    def generate_cticons(self):
        fileprocess_placement = self.common.ct_config.file_process.get("placement", {})
        file = fileprocess_placement.get("ct_icons", "ct_icons.tpl.png")
        file = f"{self.common.ct_config.pack_path}/file/{file}"

        os.makedirs(get_dir(file), exist_ok=True)
        self.common.ct_config.get_cticon().save(file)

    def patch_image(self) -> None:
        """
        Convert .png image into the format wrote in convert_file
        """

        img_encode = self.common.ct_config.file_process.get("img_encode", {})
        image_amount = len(img_encode)

        for i, (file, data) in enumerate(img_encode.items()):
            self.common.gui_main.progress(
                statut=self.common.translate("Converting images") + f"\n({i + 1}/{image_amount}) {file}",
                add=1
            )

            img.encode(
                file=f"{self.common.ct_config.pack_path}/file/{file}",
                format=data.get("format", "TEX.RGB565"),
                dest_file=f"{self.common.ct_config.pack_path}/file/{data.get('dest', None)}"
            )

    def generate_image(self, generator: dict) -> Image.Image:
        def get_layer_xy(layer: dict) -> tuple:
            return (
                int(layer.get("x", 0) * generator["width"]),
                int(layer.get("y", 0) * generator["height"])
            )

        def get_layer_bbox(layer: dict) -> tuple:
            return (
                int(layer.get("x_start", 0) * generator["width"]),
                int(layer.get("y_start", 0) * generator["height"]),
                int(layer.get("x_end", 1) * generator["width"]),
                int(layer.get("y_end", 1) * generator["height"])
            )

        def get_layer_size(layer: dict) -> tuple:
            x1, y1, x2, y2 = get_layer_bbox(layer)
            return x2-x1, y2-y1

        image = Image.new(
            generator.get("format", "RGB"),
            (generator["width"], generator["height"]),
            tuple(generator.get("color", [0]))
        )
        draw = ImageDraw.Draw(image)

        for layer in generator["layers"]:
            if "type" not in layer: continue
            if layer["type"] == "color":
                draw.rectangle(
                    get_layer_bbox(layer),
                    tuple(layer.get("color", [0]))
                )
            if layer["type"] == "image":
                layer_image = Image.open(f'{self.common.ct_config.pack_path}/file/{layer["path"]}')
                layer_image = layer_image.resize(get_layer_size(layer)).convert("RGBA")
                image.paste(
                    layer_image,
                    box=get_layer_bbox(layer),
                    mask=layer_image
                )
            if layer["type"] == "text":
                font = ImageFont.truetype(
                    font=f'{self.common.ct_config.pack_path}/file/{layer["font"]}' if "font" in layer else None,
                    size=int(layer.get("text_size", 0.1) * generator["height"]),
                )
                draw.text(
                    get_layer_xy(layer),
                    text=layer.get("text", "<Missing text>"),
                    fill=tuple(layer.get("color", 255)),
                    font=font
                )

        return image

    def generate_all_image(self) -> None:
        for file, generator in self.common.ct_config.file_process.get("img_generator", {}).items():
            file = f"{self.common.ct_config.pack_path}/file/{file}"
            os.makedirs(get_dir(file), exist_ok=True)
            self.generate_image(generator).save(file)

    def patch_tracks(self) -> None:
        """
        Download track's wu8 file and convert them to szs
        """
        thread_list = {}

        def add_process(track) -> None:
            """
            a "single thread" to download, check sha1 and convert a track
            :param track: the track that will be patched
            :return: 0 if no error occured
            """
            try: track.convert_wu8_to_szs()
            except Exception as e:
                self.common.log_error()
                raise e

        def clean_process() -> int:
            """
            Check if a track conversion ended, and remove them from thread_list
            :return: 0 if thread_list is empty, else 1
            """
            nonlocal thread_list

            for track_key, thread in thread_list.copy().items():
                if not thread.is_alive():  # if conversion ended
                    thread_list.pop(track_key)
                if not (any(thread_list.values())): return 1  # if there is no more process

            return bool(thread_list)

        total_track = self.common.ct_config.get_tracks_count()
        self.common.gui_main.progress(max=total_track, indeter=False, show=True)

        for i, track in enumerate(self.common.ct_config.get_tracks_and_arenas()):
            while True:
                max_process = self.common.gui_main.intvar_process_track.get()
                if len(thread_list) < max_process:
                    thread_list[track.sha1] = Thread(target=add_process, args=[track])
                    thread_list[track.sha1].setDaemon(True)
                    thread_list[track.sha1].start()
                    self.common.gui_main.progress(
                        statut=self.common.translate(
                            "Converting tracks", f"\n({i + 1}/{total_track})\n",
                            "\n".join(thread_list.keys())
                        ),
                        add=1
                    )
                    break
                clean_process()

        while clean_process() != 1: pass  # End the process if all process ended
