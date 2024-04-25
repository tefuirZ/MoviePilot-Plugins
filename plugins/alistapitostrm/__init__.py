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
    plugin_version = "2.7"
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
    # 任务执行间隔
    _cron = None
    _onlyonce = False
    _notify = False
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._root_path = config.get("root_path")
            self._site_url = config.get("site_url")
            self._target_directory = config.get("target_directory")
            ignored_directories_str = config.get("ignored_directories")
            self._ignored_directories = [d.strip() for d in ignored_directories_str.split(',') if d.strip()]
            self._token = config.get("token")
            self._cron = config.get("cron")
            self._notify = config.get("notify")
            self._onlyonce = config.get("onlyonce")


        if self._onlyonce:
            logger.info("Strm File Creator 插件初始化完成")
            # 确保配置完全后，启动文件生成过程
            self._scheduler.add_job(func=self.start_file_creation, trigger='date',
                                    run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                    name="alist生成strm文件")
            self._onlyonce = False
            self.update_config({
                "onlyonce": False,
                "cron": self._cron,
                "enabled": self._enabled,
                "root_path": self._root_path,
                "notify": self._notify,
                "site_url": self._site_url,
                "target_directory": self._target_directory,
                "ignored_directories": self._ignored_directories,
                "token": self._token,
            })

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def start_file_creation(self):
        logger.info('脚本运行中，因避免alistapi阈值保护，时间会长点。。。。。。')
        json_structure = {}
        base_url = self._site_url + '/d' + self._root_path + '/'
        self.traverse_directory(self._root_path, json_structure, base_url, self._target_directory)
        os.makedirs(self._target_directory, exist_ok=True)

        # 启动线程来生成strm文件
        thread = threading.Thread(target=self.create_strm_files,
                                  args=(json_structure, self._target_directory, base_url))

        thread.start()
        thread.join()
        logger.info(f" 源目录下的所有视频文件的strm文件已经创建完成，脚本自动停用")

        if self._notify:
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【alist生成strm文件】",
                text=f"批量创建strm文件成功\n"
                     f"清理备份数量 {del_cnt}\n"
                     f"剩余备份数量 {bk_cnt - del_cnt}")

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
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/alistapitostrmfile",
            "endpoint": self.start_file_creation,
            "methods": ["GET"],
            "summary": "alist生成strm文件",
            "description": "alist生成strm文件",
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        if self._enabled and self._cron:
            return [{
                "id": "alistapitostrmfile",
                "name": "alist创建strm文件定时服务",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.start_file_creation,
                "kwargs": {}
            }]

    def backup(self) -> schemas.Response:
        """
        API调用备份
        """
        success, msg = self.start_file_creation(),
        return schemas.Response(
            success=success,
            message=msg
        )

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
                                                   'model': 'notify',
                                                   'label': '发送通知',
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
                                           'md': 4
                                       },
                                       'content': [
                                           {
                                               'component': 'VTextField',
                                               'props': {
                                                   'model': 'root_path',
                                                   'label': 'alist根路径',
                                                   'placeholder': '/aliyun'
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
                                                   'model': 'cron',
                                                   'label': '定时任务周期',
                                                   'placeholder': '五位cron表达式'
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
               ], {
                   'root_path': self._root_path,
                   'site_url': self._site_url,
                   'token': self._token,
                   'target_directory': self._target_directory,
                   'ignored_directories': ','.join(self._ignored_directories) if isinstance(
                       self._ignored_directories, list) else '',
                   'cron': self._cron,
                   'enabled': self._enabled,
                   'notify': self._notify,
                   'onlyonce': self._onlyonce,

           }

    def get_page(self) -> List[dict]:
        pass

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
