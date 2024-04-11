from app.plugins import _PluginBase
from typing import Any, List, Dict, Tuple
from app.log import logger
from app.utils.string import StringUtils
import urllib
from time import sleep
import requests
import json
import configparser
import os



class FileSystemTraversalPlugin(_PluginBase):
    # 插件名称
    plugin_name = "alist-api to strm"
    # 插件描述
    plugin_desc = "通过alist api 批量生成strm文件"
    # 插件图标
    plugin_icon = "download.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "tefuir"
    # 作者主页
    author_url = "https://github.com/tefuirzt"
    # 插件配置项ID前缀
    plugin_config_prefix = "alistapitostrm_"
    # 加载顺序
    plugin_order = 28
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _downloader = None
    _is_paused = False
    _save_path = None
    _torrent_urls = None
    qb = None
    tr = None
    site = None

    def __init__(self, config_file='config.ini'):
        super().__init__()
        # 初始化默认值或者空值
        self.root_path = None
        self.site_url = None
        self.target_directory = None
        self.username = None
        self.password = None
        # 登录并获取token
        def update_config(self, config_updates):
            """
            根据提供的字典更新配置项。
            :param config_updates: 一个包含配置更新的字典。
            """
            for key, value in config_updates.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    
        self.login()

    def login(self):
        api_base_url = self.site_url + "/api"
        UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
        login_path = "/auth/login"
        url_login = api_base_url + login_path

        payload_login = json.dumps({
            "username": self.username,
            "password": self.password
        })

        headers_login = {
            'User-Agent': UserAgent,
            'Content-Type': 'application/json'
        }

        response_login = requests.post(url_login, headers=headers_login, data=payload_login)
        self.token = json.loads(response_login.text)['data']['token']



    def traverse_directory(self, path, json_structure):
        directory_info = self.list_directory(path)
        if directory_info.get('data') and directory_info['data'].get('content'):
            for item in directory_info['data']['content']:
                if item['is_dir']:
                    new_path = os.path.join(path, item['name'])
                    sleep(1)
                    if new_path in self.traversed_paths:
                        continue
                    self.traversed_paths.append(new_path)
                    new_json_object = {}
                    json_structure[item['name']] = new_json_object
                    self.traverse_directory(new_path, new_json_object)
                elif self.is_video_file(item['name']):
                    json_structure[item['name']] = {
                        'type': 'file',
                        'size': item['size'],
                        'modified': item['modified']
                    }

    def list_directory(self, path):
        url_list = self.api_base_url + "/fs/list"
        payload_list = json.dumps({
            "path": path,
            "password": "",
            "page": 1,
            "per_page": 0,
            "refresh": False
        })
        headers_list = {
            'Authorization': self.token,
            'User-Agent': UserAgent,
            'Content-Type': 'application/json'
        }
        response_list = requests.post(url_list, headers=headers_list, data=payload_list)
        return json.loads(response_list.text)

    def is_video_file(self, filename):
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']
        return any(filename.lower().endswith(ext) for ext in video_extensions)

    def create_strm_files(self, json_structure, target_directory, base_url, current_path=''):
        for name, item in json_structure.items():
            if isinstance(item, dict) and item.get('type') == 'file' and self.is_video_file(name):
                strm_filename = name.rsplit('.', 1)[0] + '.strm'
                strm_path = os.path.join(target_directory, current_path, strm_filename)

                encoded_file_path = urllib.parse.quote(os.path.join(current_path.replace('\\', '/'), name))
                video_url = base_url + encoded_file_path

                with open(strm_path, 'w', encoding='utf-8') as strm_file:
                    strm_file.write(video_url)
            elif isinstance(item, dict):
                new_directory = os.path.join(target_directory, current_path, name)
                os.makedirs(new_directory, exist_ok=True)
                self.create_strm_files(item, target_directory, base_url, os.path.join(current_path, name))

    def traverse_and_create_strm_files(self):
        json_structure = {}
        self.traverse_directory(self.root_path, json_structure)

        os.makedirs(self.target_directory, exist_ok=True)

        base_url = self.site_url + '/d' + self.root_path + '/'
        sleep(10)
        create_strm_files(json_structure, self.target_directory, base_url)


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
                                            'label': '启用插件',
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
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
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
                                            'model': 'cron',
                                            'label': '生成周期',
                                            'placeholder': '0 0 * * *'
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
                                            'model': 'site_url)',
                                            'label': 'alist地址',
                                            'placeholder': 'https://example.com'
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
                                            'model': 'username',
                                            'label': 'alist用户名',
                                            'placeholder': 'admin'
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
                                            'model': 'password',
                                            'label': 'alist密码',
                                            'placeholder': 'password'
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
                                            'model': 'target_directory',
                                            'label': 'strm生成路径',
                                            'placeholder': '/path/to/strm'
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
                                            'model': 'root_path',
                                            'label': 'alist上的路径',
                                            'placeholder': '/alist/tianyi'
                                        }
                                    }
                                ]

                            }
                        ]
                    },

                ]
            }
        ], {
            "enabled": False,
            "cron": "",
            "onlyonce": False,
            "site_url": "",
            "username": "",
            "password": "",
            "target_directory": "",
            "root_path": ""
        }
