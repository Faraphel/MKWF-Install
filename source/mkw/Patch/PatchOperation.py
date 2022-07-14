import re
from abc import ABC, abstractmethod
from io import BytesIO
from typing import IO

from PIL import Image, ImageDraw, ImageFont

from source.mkw.Patch import *
from source.wt import img, bmg
from source.wt import wstrt as wstrt

Patch: any
Layer: any


class PatchOperation:
    """
    Represent an operation that can be applied onto a patch to modify it before installing
    """

    def __new__(cls, name) -> "Operation":
        """
        Return an operation from its name
        :return: an Operation from its name
        """
        for subclass in filter(lambda subclass: subclass.type == name, cls.Operation.__subclasses__()):
            return subclass
        raise InvalidPatchOperation(name)

    class Operation(ABC):
        @abstractmethod
        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            """
            patch a file and return the new file_path (if changed) and the new content of the file
            """

    class Special(Operation):
        """
        use a file defined as special in the patch to replate the current file content
        """

        type = "special"

        def __init__(self, name: str):
            self.name = name

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            patch_content = patch.special_file[self.name]
            patch_content.seek(0)
            return file_name, patch_content

    class Rename(Operation):
        """
        Rename the output file
        """

        type = "rename"

        def __init__(self, name: str):
            self.name = name

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            return self.name, file_content

    class ImageGenerator(Operation):
        """
        generate a new image based on a file and apply a generator on it
        """

        type = "img-generate"

        def __init__(self, layers: list[dict]):
            self.layers: list["Layer"] = [self.Layer(layer) for layer in layers]

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            image = Image.open(file_content).convert("RGBA")

            for layer in self.layers:
                image = layer.patch_image(patch, image)

            patch_content = BytesIO()
            image.save(patch_content, format="PNG")
            patch_content.seek(0)

            return file_name, patch_content

        class Layer:
            """
            represent a layer for an image generator
            """

            def __new__(cls, layer: dict) -> "Layer":
                """
                return the correct type of layer corresponding to the layer mode
                :param layer: the layer to load
                """
                for subclass in filter(lambda subclass: subclass.type == layer["type"],
                                       cls.AbstractLayer.__subclasses__()):
                    layer.pop("type")
                    return subclass(**layer)
                raise InvalidImageLayerType(layer["type"])

            class AbstractLayer(ABC):
                def get_bbox(self, image: Image.Image) -> tuple:
                    """
                    return a tuple of a bbox from x1, x2, y1, y2
                    if float, calculate the position like a percentage on the image
                    if int, use directly the position
                    """
                    if isinstance(x1 := self.x1, float): x1 = int(x1 * image.width)
                    if isinstance(y1 := self.y1, float): y1 = int(y1 * image.height)
                    if isinstance(x2 := self.x2, float): x2 = int(x2 * image.width)
                    if isinstance(y2 := self.y2, float): y2 = int(y2 * image.height)

                    return x1, y1, x2, y2

                def get_bbox_size(self, image: Image.Image) -> tuple:
                    """
                    return the size that a layer use on the image
                    """
                    x1, y1, x2, y2 = self.get_bbox(image)
                    return x2 - x1, y2 - y1

                def get_font_size(self, image: Image.Image) -> int:
                    """
                    return the font_size of a layer
                    """
                    return int(self.font_size * image.height) if isinstance(self.font_size, float) else self.font_size

                def get_layer_position(self, image: Image.Image) -> tuple:
                    """
                    return a tuple of the x and y position
                    if x / y is a float, calculate the position like a percentage on the image
                    if x / y is an int, use directly the position
                    """
                    if isinstance(x := self.x, float): x = int(x * image.width)
                    if isinstance(y := self.y, float): y = int(y * image.height)

                    return x, y

                @abstractmethod
                def patch_image(self, patch: "Patch", image: Image.Image) -> Image.Image:
                    """
                    Patch an image with the actual layer. Return the new image.
                    """

            class ColorLayer(AbstractLayer):
                """
                Represent a layer that fill a rectangle with a certain color on the image
                """
                type = "color"

                def __init__(self, color: tuple[int] = (0,), x1: int | float = 0, y1: int | float = 0,
                             x2: int | float = 1.0, y2: int | float = 1.0):
                    self.x1: int | float = x1
                    self.y1: int | float = y1
                    self.x2: int | float = x2
                    self.y2: int | float = y2
                    self.color: tuple[int] = tuple(color)

                def patch_image(self, patch: "Patch", image: Image.Image):
                    draw = ImageDraw.Draw(image)
                    draw.rectangle(self.get_bbox(image), fill=self.color)

                    return image

            class ImageLayer(AbstractLayer):
                """
                Represent a layer that paste an image on the image
                """
                type = "image"

                def __init__(self, image_path: str, x1: int | float = 0, y1: int | float = 0,
                             x2: int | float = 1.0, y2: int | float = 1.0):
                    self.x1: int | float = x1
                    self.y1: int | float = y1
                    self.x2: int | float = x2
                    self.y2: int | float = y2
                    self.image_path: str = image_path

                def patch_image(self, patch: "Patch", image: Image.Image) -> Image.Image:
                    # check if the path is outside of the allowed directory
                    layer_image_path = patch.path / self.image_path
                    if not layer_image_path.is_relative_to(patch.path):
                        raise PathOutsidePatch(layer_image_path, patch.path)

                    # load the image that will be pasted
                    layer_image = Image.open(layer_image_path.resolve()) \
                                       .resize(self.get_bbox_size(image)) \
                                       .convert("RGBA")

                    # paste onto the final image the layer with transparency support
                    image.alpha_composite(
                        layer_image,
                        dest=self.get_bbox(image)[:2],
                    )

                    return image

            class TextLayer(AbstractLayer):
                """
                Represent a layer that write a text on the image
                """
                type = "text"

                def __init__(self, text: str, font_path: str | None = None, font_size: int = 10,
                             color: tuple[int] = (255,),
                             x: int | float = 0, y: int | float = 0):
                    self.x: int = x
                    self.y: int = y
                    self.font_path: str | None = font_path
                    self.font_size: int = font_size
                    self.color: tuple[int] = tuple(color)
                    self.text: str = text

                def patch_image(self, patch: "Patch", image: Image.Image) -> Image.Image:
                    draw = ImageDraw.Draw(image)

                    if self.font_path is not None:
                        font_image_path = patch.path / self.font_path
                        if not font_image_path.is_relative_to(patch.path):
                            raise PathOutsidePatch(font_image_path, patch.path)
                    else:
                        font_image_path = None

                    font = ImageFont.truetype(
                        font=str(font_image_path.resolve())
                        if isinstance(font_image_path, Path) else
                        font_image_path,
                        size=self.get_font_size(image)
                    )
                    draw.text(
                        self.get_layer_position(image),
                        text=patch.safe_eval(self.text, multiple=True),
                        fill=self.color,
                        font=font
                    )

                    return image

    class ImageEncoder(Operation):
        """
        encode an image to a game image file
        """

        type = "img-encode"

        def __init__(self, encoding: str = "CMPR"):
            """
            :param encoding: compression of the image
            """
            self.encoding: str = encoding

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            """
            Patch a file to encode it in a game image file
            :param patch: the patch that is applied
            :param file_name: the file_name of the file
            :param file_content: the content of the file
            :return: the new name and new content of the file
            """
            # remove the last extension of the filename
            patched_file_name = file_name.rsplit(".", 1)[0]
            patch_content = BytesIO(img.encode_data(file_content.read(), self.encoding))

            return patched_file_name, patch_content

    class ImageDecoder(Operation):
        """
        decode a game image to a image file
        """

        type = "img-decode"

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            """
            Patch a file to encode it in a game image file
            :param patch: the patch that is applied
            :param file_name: the file_name of the file
            :param file_content: the content of the file
            :return: the new name and new content of the file
            """
            patch_content = BytesIO(img.decode_data(file_content.read()))
            return f"{file_name}.png", patch_content

    class BmgEditor(Operation):
        """
        edit a bmg
        """

        type = "bmg-edit"

        def __init__(self, layers: list[dict]):
            """
            :param layers: layers
            """
            self.layers = layers

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            decoded_content = bmg.decode_data(file_content.read())

            for layer in self.layers:
                decoded_content = self.Layer(layer).patch_bmg(patch, decoded_content)

            patch_content = BytesIO(bmg.encode_data(decoded_content))
            return file_name, patch_content

        class Layer:
            """
            represent a layer for a bmg-edit
            """

            def __new__(cls, layer: dict) -> "Layer":
                """
                return the correct type of layer corresponding to the layer mode
                :param layer: the layer to load
                """
                for subclass in filter(lambda subclass: subclass.mode == layer["mode"],
                                       cls.AbstractLayer.__subclasses__()):
                    layer.pop("mode")
                    return subclass(**layer)
                raise InvalidBmgLayerMode(layer["mode"])

            class AbstractLayer(ABC):
                @abstractmethod
                def patch_bmg(self, patch: "Patch", decoded_content: str) -> str:
                    """
                    Patch a bmg with the actual layer. Return the new bmg content.
                    """

            class IDLayer(AbstractLayer):
                """
                Represent a layer that replace bmg entry by their ID
                """

                mode = "id"

                def __init__(self, template: dict[str, str]):
                    self.template = template

                def patch_bmg(self, patch: "Patch", decoded_content: str) -> str:
                    return decoded_content + "\n" + ("\n".join(
                        [f"  {id}\t= {patch.safe_eval(repl, multiple=True)}" for id, repl in self.template.items()]
                    )) + "\n"
                    # add new bmg definition at the end of the bmg file, overwritting old id.

            class RegexLayer(AbstractLayer):
                """
                Represent a layer that replace bmg entry by matching them with a regex
                """

                mode = "regex"

                def __init__(self, template: dict[str, str]):
                    self.template = template

                def patch_bmg(self, patch: "Patch", decoded_content: str) -> str:
                    # TODO : use regex in a better way to optimise speed

                    new_bmg_lines: list[str] = []
                    for line in decoded_content.split("\n"):
                        if (match := re.match(r"^ {2}(?P<id>.*?)\t= (?P<value>.*)$", line, re.DOTALL)) is None:
                            # check if the line match a bmg definition, else ignore
                            # bmg definition is : 2 spaces, a bmg id, a tab, an equal sign, a space and the bmg text
                            continue

                        new_bmg_id: str = match.group("id")
                        new_bmg_def: str = match.group("value")
                        for pattern, repl in self.template.items():
                            new_bmg_def = re.sub(
                                pattern,
                                patch.safe_eval(repl, multiple=True),
                                new_bmg_def,
                                flags=re.DOTALL
                            )
                            # match a pattern from the template, and replace it with its repl

                        new_bmg_lines.append(f"  {new_bmg_id}\t={new_bmg_def}")

                    return decoded_content + "\n" + ("\n".join(new_bmg_lines)) + "\n"
                    # add every new line to the end of the decoded_bmg, old bmg_id will be overwritten.

    class StrEditor(Operation):
        """
        patch the main.dol file
        """

        type = "str-edit"

        def __init__(self, region: int = None, https: str = None, domain: str = None, sections: list[str] = None):
            self.region = region
            self.https = https
            self.domain = domain
            self.sections = sections

        def patch(self, patch: "Patch", file_name: str, file_content: IO) -> (str, IO):
            checked_sections: list[Path] = []

            for section in self.sections if self.sections is not None else []:
                section_path = patch.path / section
                if not section_path.is_relative_to(patch.path):
                    raise PathOutsidePatch(section_path, patch.path)

                checked_sections += section_path
            # for every file in the sections, check if they are inside the patch.

            patch_content = BytesIO(
                wstrt.patch_data(
                    file_content.read(),
                    region=self.region,
                    https=self.https,
                    domain=self.domain,
                    sections=checked_sections
                )
            )

            return file_name, patch_content