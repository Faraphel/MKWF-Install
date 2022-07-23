import tkinter
from pathlib import Path
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from source.translation import translate as _


class Window(tkinter.Toplevel):
    """
    A window that let the user select MyStuff pack for a MKWF patch
    """

    def __init__(self):
        super().__init__()
        self.title(_("CONFIGURE_MYSTUFF_PATCH"))
        self.resizable(False, False)
        self.grab_set()  # the others window will be disabled, keeping only this one activated

        self.disabled_text: str = _("<", "DISABLED", ">")
        self.master.options["mystuff_pack_selected"] = self.master.options["mystuff_pack_selected"]

        self.frame_profile = ttk.Frame(self)
        self.frame_profile.grid(row=1, column=1, sticky="NEWS")

        self.combobox_profile = ttk.Combobox(self.frame_profile, justify=tkinter.CENTER)
        self.combobox_profile.grid(row=1, column=1, sticky="NEWS")
        self.combobox_profile.bind("<<ComboboxSelected>>", self.select_profile)

        self.button_new_profile = ttk.Button(
            self.frame_profile,
            text=_("NEW_PROFILE"),
            command=self.new_profile
        )
        self.button_new_profile.grid(row=1, column=2, sticky="NEWS")

        self.button_delete_profile = ttk.Button(
            self.frame_profile,
            text=_("DELETE_PROFILE"),
            command=self.delete_profile
        )
        self.button_delete_profile.grid(row=1, column=3, sticky="NEWS")

        self.frame_mystuff_paths = ttk.Frame(self)
        self.frame_mystuff_paths.grid(row=2, column=1, sticky="NEWS")
        self.frame_mystuff_paths.grid_columnconfigure(1, weight=1)

        self.listbox_mystuff_paths = tkinter.Listbox(self.frame_mystuff_paths)
        self.listbox_mystuff_paths.grid(row=1, column=1, sticky="NEWS")
        self.scrollbar_mystuff_paths = ttk.Scrollbar(
            self.frame_mystuff_paths,
            command=self.listbox_mystuff_paths.yview
        )
        self.scrollbar_mystuff_paths.grid(row=1, column=2, sticky="NS")
        self.listbox_mystuff_paths.configure(yscrollcommand=self.scrollbar_mystuff_paths.set)

        self.frame_mystuff_paths_action = ttk.Frame(self)
        self.frame_mystuff_paths_action.grid(row=3, column=1, sticky="NEWS")

        self.button_add_mystuff_path = ttk.Button(
            self.frame_mystuff_paths_action,
            text=_("ADD_MYSTUFF"),
            command=self.add_mystuff_path
        )
        self.button_add_mystuff_path.grid(row=1, column=1)

        self.button_remove_mystuff_path = ttk.Button(
            self.frame_mystuff_paths_action,
            text=_("REMOVE_MYSTUFF"),
            command=self.remove_mystuff_path
        )
        self.button_remove_mystuff_path.grid(row=1, column=2)

        self.refresh_profiles()
        self.select_profile()

    def refresh_profiles(self) -> None:
        """
        Refresh all the profile
        """

        combobox_values = [self.disabled_text, *self.master.options["mystuff_packs"]]
        self.combobox_profile.configure(values=combobox_values)
        self.combobox_profile.current(combobox_values.index(
            self.master.options["mystuff_pack_selected"]
            if self.master.options["mystuff_pack_selected"] in self.master.options["mystuff_packs"] else
            self.disabled_text
        ))

    def select_profile(self, event: tkinter.Event = None, profile_name: str = None) -> None:
        """
        Select another profile
        """

        profile_name = self.combobox_profile.get() if profile_name is None else profile_name
        self.combobox_profile.set(profile_name)
        self.master.options["mystuff_pack_selected"] = profile_name
        self.listbox_mystuff_paths.delete(0, tkinter.END)

        is_disabled = (profile_name == self.disabled_text)
        for children in self.frame_mystuff_paths_action.children.values():
            children.configure(state=tkinter.DISABLED if is_disabled else tkinter.NORMAL)
        if is_disabled: return

        profile_data = self.master.options["mystuff_packs"][profile_name]

        for path in profile_data["paths"]:
            self.listbox_mystuff_paths.insert(tkinter.END, path)

    def new_profile(self) -> None:
        """
        Save the new profile
        """
        profile_name: str = self.combobox_profile.get()
        if profile_name in self.master.options["mystuff_packs"]:
            messagebox.showerror(_("ERROR"), _("MYSTUFF_PROFILE_ALREADY_EXIST"))
            return

        for banned_char in "<>":
            if banned_char in profile_name:
                messagebox.showerror(_("ERROR"), _("MYSTUFF_PROFILE_FORBIDDEN_NAME"))
                return

        self.master.options["mystuff_packs"][profile_name] = {"paths": []}
        self.refresh_profiles()
        self.select_profile(profile_name=profile_name)

    def delete_profile(self) -> None:
        """
        Delete the currently selected profile
        """
        profile_name: str = self.combobox_profile.get()
        self.master.options["mystuff_packs"][self.master.options["mystuff_pack_selected"]].pop(profile_name)

        self.select_profile()

    def add_mystuff_path(self) -> None:
        """
        Add a new path to the currently selected MyStuff profile
        """

        if (mystuff_path := filedialog.askdirectory(title=_("SELECT_MYSTUFF"), mustexist=True)) is None: return
        mystuff_path = Path(mystuff_path)

        self.master.options["mystuff_packs"][self.master.options["mystuff_pack_selected"]]["paths"].append(
            str(mystuff_path.resolve())
        )

        self.select_profile()

    def remove_mystuff_path(self) -> None:
        """
        Remove the selected MyStuff path from the profile
        :return:
        """
        selections = self.listbox_mystuff_paths.curselection()
        if not selections: return

        for selection in selections:
            self.master.options["mystuff_packs"][self.master.options["mystuff_pack_selected"]]["paths"].pop(selection)

        self.select_profile()