import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class DataManager:
    """centralized data management for all json files"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self._cache = {}
        self._locks = {}
        self._autosave_tasks = {}

    def _get_lock(self, filename: str) -> Lock:
        """get or create a lock for a specific file"""
        if filename not in self._locks:
            self._locks[filename] = Lock()
        return self._locks[filename]

    def load(self, filename: str, default: Any = None) -> Any:
        """load data from json file with caching"""
        if filename in self._cache:
            return self._cache[filename]

        file_path = self.data_dir / f"{filename}.json"

        with self._get_lock(filename):
            if not file_path.exists():
                self._cache[filename] = default if default is not None else {}
                return self._cache[filename]

            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    self._cache[filename] = data
                    return data
            except (json.JSONDecodeError, IOError):
                self._cache[filename] = default if default is not None else {}
                return self._cache[filename]

    def save(self, filename: str, data: Any = None) -> bool:
        """save data to json file"""
        if data is not None:
            self._cache[filename] = data
        elif filename not in self._cache:
            return False

        file_path = self.data_dir / f"{filename}.json"

        with self._get_lock(filename):
            try:
                with open(file_path, "w") as f:
                    json.dump(self._cache[filename], f, indent=2)
                return True
            except IOError:
                return False

    def get(self, filename: str, key: str, default: Any = None) -> Any:
        """get a specific key from a data file"""
        data = self.load(filename)
        if isinstance(data, dict):
            return data.get(key, default)
        return default

    def set(self, filename: str, key: str, value: Any) -> bool:
        """set a specific key in a data file"""
        data = self.load(filename)
        if isinstance(data, dict):
            data[key] = value
            return self.save(filename)
        return False

    def delete_key(self, filename: str, key: str) -> bool:
        """delete a specific key from a data file"""
        data = self.load(filename)
        if isinstance(data, dict) and key in data:
            del data[key]
            return self.save(filename)
        return False

    def append(self, filename: str, key: str, value: Any) -> bool:
        """append to a list in a data file"""
        data = self.load(filename)
        if isinstance(data, dict):
            if key not in data:
                data[key] = []
            if isinstance(data[key], list):
                data[key].append(value)
                return self.save(filename)
        return False

    def increment(self, filename: str, key: str, amount: int = 1) -> int:
        """increment a numeric value in a data file"""
        data = self.load(filename)
        if isinstance(data, dict):
            if key not in data:
                data[key] = 0
            if isinstance(data[key], (int, float)):
                data[key] += amount
                self.save(filename)
                return data[key]
        return 0

    def get_all(self, filename: str) -> Dict:
        """get all data from a file"""
        return self.load(filename, {})

    def clear_cache(self, filename: Optional[str] = None):
        """clear cached data"""
        if filename:
            self._cache.pop(filename, None)
        else:
            self._cache.clear()


_data_manager = None


def get_data_manager() -> DataManager:
    """get or create the global data manager instance"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager
