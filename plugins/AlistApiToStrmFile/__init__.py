import urllib
import requests
import configparser
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.log import logger
from app.plugins import _PluginBase
from app.core.event import eventmanager
from app.schemas.types import EventType
from app.utils.system import SystemUtils
import threading
from time import sleep



class AlistApiToStrmFile(_PluginBase):
    # 插件属性
    plugin_name = "alist生成strm文件"
    plugin_desc = "通过alist-api在指定目录下创建strm文件"
    plugin_icon = "https://img.679865.xyz/1/65ae8e98e6095.ico"
    plugin_color = "#3B5E8E"
    plugin_version = "1.0.0"
    plugin_author = "tefuir"
    author_url = "https://github.com/tefuirZ"
    plugin_config_prefix = "alistapito_strmfile_"
    plugin_order = 30
    auth_level = 1

    _enabled = False
    _root_path = None  # Modified: Set default value to None
    _site_url = None  # Modified: Set default value to None
    _target_directory = None  # Modified: Set default value to None
    _ignored_directories = None  # Modified: Set default value to None
    _token = None  # Modified: Set default value to None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            self._root_path = config.get("root_path", self._root_path)
            self._site_url = config.get("site_url", self._site_url)
            self._target_directory = config.get("target_directory", self._target_directory)
            ignored_directories_str = config.get("ignored_directories", "")
            self._ignored_directories = [d.strip() for d in ignored_directories_str.split(',') if d.strip()]
            self._token = config.get("token", "")

        if self._enabled:
            logger.info("Strm File Creator 插件初始化完成")
            thread = threading.Thread(target=self.create_strm_files)
            thread.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command():
        pass

    def get_api(self):
        pass

    def get_form(self):
        return [
            {
                'component': 'VSwitch',
                'props': {
                    'model': 'enabled',
                    'label': '启用插件',
                }
            },
            {
                'component': 'VTextField',
                'props': {
                    'model': 'root_path',
                    'label': 'alist根路径',
                }
            },
            {
                'component': 'VTextField',
                'props': {
                    'model': 'site_url',
                    'label': 'alist地址',
                }
            },
            {
                'component': 'VTextField',
                'props': {
                    'model': 'target_directory',
                    'label': '目标目录',
                }
            },
            {
                'component': 'VTextField',
                'props': {
                    'model': 'ignored_directories',
                    'label': '忽略目录',
                }
            },
            {
                'component': 'VTextField',
                'props': {
                    'model': 'token',
                    'label': 'alist的令牌',
                }
            }
        ], {
            "enabled": self._enabled,
            "root_path": self._root_path,
            "site_url": self._site_url,
            "target_directory": self._target_directory,
            "ignored_directories": ','.join(self._ignored_directories),
            "token": self._token
        }
    def get_page(self):
        pass

    def create_strm_files(self):
        print('脚本运行中。。。。。。。')
        json_structure = {}
        base_url = site_url + '/d' + root_path + '/'
        traverse_directory(root_path, json_structure, base_url, target_directory)
        os.makedirs(target_directory, exist_ok=True)
        create_strm_files(json_structure, target_directory, base_url)
        print('所有strm文件创建完成')

    def stop_service(self):
        pass


def requests_retry_session(
        retries=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504),
        session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def list_directory(self, path):
    url_list = site_url + "/api/fs/list"
    payload_list = {
        "path": path,
        "password": "",
        "page": 1,
        "per_page": 0,
        "refresh": False
    }
    headers_list = {
        'Authorization': self._token,
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json'
    }
    response_list = requests_retry_session().post(url_list, headers=headers_list, json=payload_list)
    return response_list.json()


def traverse_directory(self, path, json_structure, base_url, target_directory, is_root=True):
    directory_info = self.list_directory(path)
    if directory_info.get('data') and directory_info['data'].get('content'):
        for item in directory_info['data']['content']:
            if item['is_dir']:
                new_path = os.path.join(path, item['name'])
                sleep(5)  # 为了避免请求过快被服务器限制
                traverse_directory(new_path, json_structure, base_url, target_directory, is_root=False)
            elif is_video_file(item['name']):
                json_structure[item['name']] = {
                    'type': 'file',
                    'size': item['size'],
                    'modified': item['modified']
                }

    if not is_root:
        create_strm_files(json_structure, target_directory, base_url,
                          path.replace(root_path, '').strip('/').replace('/', os.sep))


def is_video_file(self, filename):  # Modified: Add self.
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']
    return any(filename.lower().endswith(ext) for ext in video_extensions)


def create_strm_files(self, json_structure, target_directory, base_url, current_path=''):
    for name, item in json_structure.items():
        full_path = os.path.join(target_directory, current_path)
        if isinstance(item, dict) and item.get('type') == 'file':
            if not item.get('created'):
                strm_filename = name.rsplit('.', 1)[0] + '.strm'
                strm_path = os.path.join(full_path, strm_filename)

                if os.path.exists(strm_path):
                    print(f"{strm_path} 已存在，跳过创建。")
                    continue

                os.makedirs(full_path, exist_ok=True)
                encoded_file_path = urllib.parse.quote(os.path.join(current_path.replace('\\', '/'), name))
                video_url = base_url + encoded_file_path
                item['created'] = True
                with open(strm_path, 'w', encoding='utf-8') as strm_file:
                    strm_file.write(video_url)
                    print(f"{strm_path} 已创建。")
        elif isinstance(item, dict):
            new_directory = os.path.join(full_path, name)
            os.makedirs(new_directory, exist_ok=True)
            create_strm_files(item, target_directory, base_url, os.path.join(current_path, name))