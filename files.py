from __future__ import annotations
from datetime import datetime
from functools import cache
import os
import re
from typing import Any, Union
import psutil

from utils import platform

if platform() == "windows":
    import win32security
else:
    import pwd



class Path:
    def __init__(self, path: str | list[str] | None = None) -> None:
        path = path or ""
        self._separator: str = '\\' if platform() == "windows" else '/'
        if isinstance(path, list):
            while '' in path:
                path.remove('')
            path = self._separator.join(path)
        
        self._path: str = path
    
    def as_list(self) -> list[str]:
        list_version: list[str] = [
            x.strip() 
            for x in self.path.split(self._separator)
        ]
        while '' in list_version:
            list_version.remove('')
        return list_version
    
    def startswith(self, other: Path | str) -> bool:
        return self.path.startswith(str(other))
    
    def endswith(self, other: Path | str) -> bool:
        return self.path.endswith(str(other))

    def valid_dir(self) -> bool:
        if not os.path.isdir(self.path) and self.path not in (
            '',
            self.separator
        ):
            return False
        
        return True
    
    def valid_file(self) -> bool:
        if not os.path.isfile(self.path) and self.path not in (
            '',
            self.separator
        ):
            return False
        
        return True
    
    def list_items(self) -> tuple[Path, ...]:
        if self.path == '':
            return tuple(get_drives())
        
        if not self.valid_dir():
            return tuple()
        
        return tuple(Path(x) for x in os.listdir(self.path))
    
    @property
    def separator(self) -> str:
        return self._separator
    
    @property
    def path(self) -> str:
        return self._path
    
    def split(self, sep: str) -> tuple[Path, ...]:
        items: list[str] = self.path.split(sep)

        return tuple(Path(item) for item in items)
    
    @path.setter
    def path(self, value: str | list[str]) -> None:
        if isinstance(value, list):
            value = self._separator.join(value)
        
        self._path = value
    
    def __str__(self) -> str:
        return str(self.path)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Path):
            return self.path == other.path
        if isinstance(other, str):
            return self.path == other
        
        raise TypeError(
            "Can only check equality of Path object with a string or a Path"
        )
    
    def __ne__(self, other: object) -> bool:
        if isinstance(other, Path):
            return self.path != other.path
        if isinstance(other, str):
            return self.path != other
        
        raise TypeError(
            "Can only check inequality of Path object with a string or a Path"
        )

    def __repr__(self) -> str:
        return repr(self._path)
    
    def __add__(self, other: Path | str) -> Path:
        other_path: str = str(other)
        
        return Path([self.path, other_path])
    
    def __radd__(self, other: Path | str) -> Path:
        other_path: str = str(other)
        
        return Path([other_path, self.path])
    
    def __contains__(self, item: str) -> bool:
        return item in self.as_list()
    
    def __len__(self) -> int:
        return len(self.as_list())
        
    def __lt__(self, other: Path) -> bool:
        return self.path.lower() < other.path.lower()
    
    def __gt__(self, other: Path) -> bool:
        return self.path.lower() > other.path.lower()
    
    def __lte__(self, other: Path) -> bool:
        return self.path.lower() <= other.path.lower()
    
    def __gte__(self, other: Path) -> bool:
        return self.path.lower() >= other.path.lower()

    def __fspath__(self) -> str:
        return self.path
    
    def __hash__(self) -> int:
        return hash(self.path)



def get_drives() -> list[Path]:
    """Returns the path of all drives mounted on the current system."""
    return [Path(x.mountpoint) for x in psutil.disk_partitions(all=True)]


def get_folders(directory: Path) -> list[Path]:
    """
    Returns all the folders in the given file path.

    Args:
        cwd (str): The file path to find folders from

    Raises:
        FileNotFoundError: When `cwd` is not a valid directory

    Returns:
        list[str]: A list of the directories (their full paths)
    """
    if directory == '':
        return get_drives()
    
    if not directory.valid_dir():
        raise FileNotFoundError(
            f"{repr(directory)} is not a valid directory.")
    
    folders: list[Path] = []
    for item in directory.list_items():
        split_item: tuple[Path, ...] = item.split('.')
        if len(split_item) <= 1 or item.startswith('.'):
            folders.append(directory + item)
    
    return folders


def get_files_folders(file_path: Path) -> tuple[list[Path], list[Path]]:
    """
    Gets all the files and folders in a given directory.

    Args:
        file_path (Path): The directory to check.

    Returns:
        tuple[list[Path], list[Path]]: A tuple containing two lists, one
            containing all folders, and one containing all files. This
            is in the format (FILES, FOLDERS).
    """
    if not file_path.valid_dir():
        raise NotADirectoryError(
            "File path expects a directory. "
            + f"{repr(file_path)} is not a directory."
        )
    items: tuple[Path, ...] = file_path.list_items()

    files: list[Path] = []
    folders: list[Path] = []

    for item in items:
        full_path: Path = file_path + item
        if os.path.isfile(full_path):
            files.append(item)
            continue
            
        folders.append(item)

    return (sorted(files), sorted(folders))


def get_file_metadata(file_path: Path) -> dict[str, Union[Path, str, datetime, None]]:
    """
    Retrieve metadata for a single file or folder.

    Args:
        file_path (str): Path to the file or folder.

    Returns:
        dict: Metadata dictionary containing owner, last modified time, and file size.
    """
    try:
        file_stats: os.stat_result = os.stat(file_path)
        owner: str = (
            _get_windows_owner(file_path) 
            if platform() == "windows" 
            else _get_unix_owner(file_stats)
        )

        

        metadata: dict[str, Union[Path, str, datetime, None]] = {
            "Path": file_path,
            "Owner": owner,
            "Last Modified": datetime.fromtimestamp(file_stats.st_mtime),
            "File Size": (
                format_size(file_stats.st_size) 
                if not os.path.isdir(file_path) 
                else None
            ),
            "Item": get_file_type(file_path),
        }

        return metadata
    
    except FileNotFoundError:
        return {"Error": f"File not found: {repr(file_path)}"}
    
    except Exception as e:
        return {"Error": str(e)}
    

def format_size(size: int | float) -> str:
    """
    Convert a file size from bytes to a human-readable format.

    Args:
        size (int): The file size in bytes.

    Returns:
        str: The file size as a formatted string.
    """
    units: list[str] = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} {units[-1]}"


def fix_path(path: Path) -> Path:
    is_windows: bool = platform() == "windows"

    if is_windows:
        path = Path(re.sub(r"(?<=:)(?!\\)", r"\\", str(path)))
        
    elif not path.startswith('/') and str(path) not in ['', '/']:
        path = Path('/') + path


    if not path.valid_dir():
        raise NotADirectoryError(f"fix_path expects a directory! {repr(path)} does not match!")

    if is_windows and not path.endswith('\\') and path != '':
        path += Path('\\')
    if (
        not is_windows
        and not path.endswith('/')
        and str(path) not in ['/', '']
    ):
        path = path + Path('/')

    if str(path) not in ('', '/', '\\'):
        path = Path(os.path.realpath(path))

    return path


def _get_windows_owner(file_path: Path) -> str:
    """Get the owner of a file or folder on Windows."""
    try:
        owner_sid: Any
        owner: str
        _: Any
        
        security_descriptor: Any = (
            win32security.GetFileSecurity( #type: ignore
                str(file_path),
                win32security.OWNER_SECURITY_INFORMATION #type: ignore
            )
        )
        owner_sid = security_descriptor.GetSecurityDescriptorOwner()

        owner, _,  _ =   win32security.LookupAccountSid( #type: ignore
            None, #type: ignore
            owner_sid
        )  
        return owner
    except Exception as e:
        print(e)
        return "Unknown Owner"
    

def _get_unix_owner(file_stats: os.stat_result) -> str:
        """Get the owner of a file or folder on Unix-like systems."""
        try:
            return pwd.getpwuid(file_stats.st_uid).pw_name #type: ignore
        except KeyError:
            return "Unknown Owner"


@cache
def get_file_type(file_path: Path) -> str:
    extension: str
    _, extension = os.path.splitext(file_path)
    if os.path.isdir(file_path): extension = "Folder"

    return extension