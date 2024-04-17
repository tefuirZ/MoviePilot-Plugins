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
from typing import List, Dict, Any, Tuple

class alistapitostrm(_PluginBase):
    # 插件属性
    plugin_name = "alist生成strm文件"
    plugin_desc = "通过alist-api在指定目录下创建strm文件"
    plugin_icon = "https://img.679865.xyz/1/65ae8e98e6095.ico"
    plugin_color = "#3B5E8E"
    plugin_version = "1.0"
    plugin_author = "tefuir"
    author_url = "https://github.com/tefuirZ"
    plugin_config_prefix = "alistapitostrmfile_"
    plugin_order = 3
    auth_level = 1

    _enabled = False
    _root_path = None
    _site_url = None
    _target_directory = None
    _ignored_directories = None
    _token = None



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
        
        # 获取插件配置和用户交互界面
        form, default_config = self.get_form()
        
        # 在此处可以处理form和default_config，例如展示给用户进行配置
        # ...
        
        thread = threading.Thread(target=self.create_strm_files,
                                  args=(self.traverse_directory(self._root_path, {}, self._site_url, self._target_directory),
                                        self._target_directory,
                                        self._site_url + '/d' + self._root_path + '/'))
        thread.start()
        logger.info('脚本运行中。。。。。。。')
        os.makedirs(self._target_directory, exist_ok=True)
        logger.info('所有strm文件创建完成')
        self._enabled = False







    def requests_retry_session(
        self,
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
        url_list = self._site_url + "/api/fs/list"
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
        response_list = self.requests_retry_session().post(url_list, headers=headers_list, json=payload_list)
        return response_list.json()

    def traverse_directory(self, path, json_structure, base_url, target_directory, is_root=True):
        directory_info = self.list_directory(path)
        if directory_info.get('data') and directory_info['data'].get('content'):
            for item in directory_info['data']['content']:
                if item['is_dir']:
                    new_path = os.path.join(path, item['name'])
                    sleep(5)
                    self.traverse_directory(new_path, json_structure, base_url, target_directory, is_root=False)
                elif self.is_video_file(item['name']):
                    json_structure[item['name']] = {
                        'type': 'file',
                        'size': item['size'],
                        'modified': item['modified']
                    }

        if not is_root:
            self.create_strm_files(json_structure, target_directory, base_url,
                                   path.replace(self._root_path, '').strip('/').replace('/', os.sep))

    def is_video_file(self, filename):
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
                        logger.info(f"{strm_path} 已存在，跳过创建。")
                        continue

                    os.makedirs(full_path, exist_ok=True)
                    encoded_file_path = urllib.parse.quote(os.path.join(current_path.replace('\\', '/'), name))
                    video_url = base_url + encoded_file_path
                    item['created'] = True
                    with open(strm_path, 'w', encoding='utf-8') as strm_file:
                        strm_file.write(video_url)
                        logger.info(f"{strm_path} 已创建。")
            elif isinstance(item, dict):
                new_directory = os.path.join(full_path, name)
                os.makedirs(new_directory, exist_ok=True)
                self.create_strm_files(item, target_directory, base_url, os.path.join(current_path, name))

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
                   {
                       'component': 'VForm',
                       'content': [
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VSwitch',
                                               'props': {
                                                   'model': 'enabled',
                                                   'label': '立即运行一次',
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'root_path',
                                                   'label': 'alist根路径',
                                               }
                                           }
                                       ]
                                   }
                               ]
                           },
                           {
                               'component': 'VRow',
                               'content': [
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'site_url',
                                                   'label': 'alist地址',
                                                   'placeholder': 'http://alist.b.com'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'token',
                                                   'label': 'alist的token',
                                                   'placeholder': 'alist-******'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'target_directory',
                                                   'label': 'strm存放路径',
                                                   'placeholder': '/home/alist/strm'
                                               }
                                           }
                                       ]
                                   },
                                   {
                                       'component': 'VCol',
                                       'props': {
                                           'cols': 12,
                                           'md': 6
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'ignored_directories',
                                                   'label': '排除路径',
                                                   'placeholder': '/img'
                                               }
                                           }
                                       ]
                                   }


                               ]
                           },


                       ]
                   }
               ],  {
            "enabled": self._enabled,
            "root_path": self._root_path,
            "site_url": self._site_url,
            "target_directory": self._target_directory,
            "ignored_directories": ','.join(self._ignored_directories) if isinstance(self._ignored_directories,
                                                                                     list) else '',
            "token": self._token
        }

    def get_page(self) -> List[dict]:
        pass

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        pass
