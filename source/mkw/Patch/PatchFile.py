from io import BytesIO
from typing import Generator

from source.mkw.Patch import *
from source.mkw.Patch.PatchOperation import PatchOperation
from source.mkw.Patch.PatchObject import PatchObject
from source.wt.szs import SZSPath


class PatchFile(PatchObject):
    """
    Represent a file from a patch
    """

    def get_source_path(self, game_subpath: Path):
        """
        Return the path of the file that the patch is applied on.
        If the configuration mode is set to "edit", then return the path of the file inside the Game
        Else, return the path of the file inside the Patch
        """
        match self.configuration["mode"]:
            case "edit":
                return game_subpath
            case _:
                return self.full_path

    def install(self, extracted_game: "ExtractedGame", game_subpath: Path) -> Generator[dict, None, None]:
        """
        patch a subfile of the game with the PatchFile
        """
        yield {"description": f"Patching {self}"}

        # check if the file should be patched considering the "if" configuration
        if self.patch.safe_eval(self.configuration["if"], extracted_game=extracted_game) == "False": return

        # check if the path to the game_subpath is inside a szs, and if yes extract it
        for szs_subpath in filter(lambda path: path.suffix == ".d",
                                  game_subpath.parent.relative_to(extracted_game.path).parents):
            szs_path = extracted_game.path / szs_subpath

            # if the archive is already extracted, ignore
            if not szs_path.exists():
                # if the szs file in the game exists, extract it
                if szs_path.with_suffix(".szs").exists():
                    SZSPath(szs_path.with_suffix(".szs")).extract_all(szs_path)

        # apply operation on the file
        patch_source: Path = self.get_source_path(game_subpath)
        patch_name: str = game_subpath.name
        patch_content: BytesIO = BytesIO(open(patch_source, "rb").read())
        # the file is converted into a BytesIO because if the mode is "edit",
        # the file is overwritten and if the content is untouched, the file will only be lost

        for operation_name, operation in self.configuration.get("operation", {}).items():
            # process every operation and get the new patch_path (if the name is changed)
            # and the new content of the patch
            patch_name, patch_content = PatchOperation(operation_name)(**operation).patch(
                self.patch, patch_name, patch_content
            )

        match self.configuration["mode"]:
            # if the mode is copy, replace the subfile in the game by the PatchFile
            case "copy" | "edit":
                # print(f"[{self.configuration['mode']}] copying {self} to {game_subpath}")

                game_subpath.parent.mkdir(parents=True, exist_ok=True)
                with open(game_subpath.parent / patch_name, "wb") as file:
                    file.write(patch_content.read())

            # if the mode is match, replace all the subfiles that match match_regex by the PatchFile
            case "match":
                for game_subfile in game_subpath.parent.glob(self.configuration["match_regex"]):
                    # disallow patching files outside of the game
                    if not game_subfile.relative_to(extracted_game.path):
                        raise PathOutsidePatch(game_subfile, extracted_game.path)
                    # patch the game with the subpatch
                    # print(f"[match] copying {self} to {game_subfile}")

                    game_subfile.parent.mkdir(parents=True, exist_ok=True)
                    with open(game_subfile, "wb") as file:
                        file.write(patch_content.read())

            # ignore if mode is "ignore", useful if the file is used as a resource for an operation
            case "ignore": pass

            # else raise an error
            case _:
                raise InvalidPatchMode(self.configuration["mode"])

        patch_content.close()