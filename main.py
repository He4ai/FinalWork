import requests
import datetime
import json
from tqdm import tqdm
import logging
import configparser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class YaDisk:
    def __init__(self, ya_token):
        self.yandex_token = 'OAuth ' + ya_token

    def _create_folder(self):
        url = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {'path': 'VK Photos'}
        headers = {'Authorization': self.yandex_token}
        response = requests.put(url, params=params, headers=headers)
        if response.status_code == 201:
            logging.info('Folder created successfully')
        elif response.status_code == 409:
            logging.info('Folder is already exists')
        else:
            logging.error(f'Failed to create folder: {response.json()["description"]}')

    def put_photo(self, photos):
        self._create_folder()

        url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        headers = {'Authorization': self.yandex_token}
        if not photos:
            logging.error('Photos were not uploaded!')
            return

        logging.info(f'Photos successfully found')
        for photo in tqdm(photos, desc='Uploading photos', unit='photo'):  # Логирование д-ий программы
            while True:  # Цикл для проверки имён файлов
                try:
                    params = {'path': f'VK Photos/{photo["file_name"]}',
                              'overwrite': False}
                    response = requests.get(url, params=params, headers=headers)
                    url_upload = response.json()['href']
                    file_response = requests.get(photo['url'])
                    response = requests.put(url_upload, headers=headers, data=file_response.content)
                    if response.status_code == 201:
                        logging.info(f'Successfully uploaded {photo["file_name"]}')
                    break
                except KeyError:
                    # Смена имени если такой файл уже есть на диске
                    if response.json()['error'] == 'DiskResourceAlreadyExistsError':
                        photo["file_name"] = self._change_name(photo["file_name"])
                    # Другие ошибки
                    else:
                        logging.error(f'{response.json()["error"]}')
                        return
        logging.info('All photos are uploaded!')

    @staticmethod
    def _change_name(file_name):  # Ф-ия для смены имени файла
        logging.info(f'A file named {file_name} already exists, generating another name')
        if '(' not in file_name:
            file_name = f'{file_name[:-4]} (1).jpg'
        else:
            file_name = (f'{file_name[:-6]}'
                         f'{int(file_name[-6]) + 1}'
                         f').jpg')
        logging.info(f'New file name: {file_name}')
        return file_name


class VKApi:

    def __init__(self, vk_id, version='5.131'):
        self.vk_id = vk_id
        self.version = version
        self.access_token = self._get_access_token()
        self.params = {'access_token': self.access_token,
                       'v': self.version}

    @staticmethod
    def _get_access_token() -> str:  # Токен доступа хранися в Ini-файле
        config = configparser.ConfigParser()
        config.read("configs.ini")
        return config["Vk"]["token"]

    def _user_id(self) -> bool:  # Ф-ия для нахождения id по никнейму
        if not self.vk_id.isdigit():
            url = 'https://api.vk.com/method/users.get'
            params = {'user_ids': self.vk_id,
                      'fields': 'domain'}
            response = requests.get(url, params={**self.params, **params})

            if response.status_code != 200:
                logging.error(f"Error fetching user ID: {response.text}")
                return False

            response_json = response.json()

            if response_json['response']:
                self.vk_id = response.json()['response'][0]['id']
                return True
            else:
                logging.error('There is no user with this nickname!')
                return False
        return True

    def get_photos(self, quantity: int = 5):
        if not self._user_id():
            return []

        url = 'https://api.vk.com/method/photos.get'
        params = {'owner_id': self.vk_id,
                  'album_id': 'profile',
                  'extended': 1,
                  'count': quantity}
        response = requests.get(url, params={**self.params, **params})

        response_json = response.json().get('response')

        if response_json is None:  # Проверка на ошибки Api
            logging.error(f'{response.json()["error"]["error_msg"]}')
            return []

        if response_json['count'] == 0:
            logging.error('The user does not have a photo or you entered the wrong ID or nickname!')
            return []

        if response_json['count'] < quantity:
            logging.info('The user has fewer photos than you specified.'
                         f'Only {response_json["count"]} photos will be uploaded.')
        return response_json['items']


class PhotoManager:  # Отдельный класс для генерации json-файла
    @staticmethod
    def create_json_file(all_photos):
        files_info = []
        file_names = []

        for photo_data in all_photos:
            file_name = f"{photo_data['likes']['count']}.jpg"
            date_str = datetime.datetime.fromtimestamp(photo_data["date"]).strftime('%Y-%m-%d')
            if file_name in file_names:
                index = file_names.index(file_name)
                files_info[index]['file_name'] = f'{files_info[index]["file_name"][:-4]} {date_str}.jpg'
                file_name = f"{file_name[:-4]} {date_str}.jpg"

            file_names.append(file_name)
            max_size = max(photo_data['sizes'], key=lambda x: (x['height'], x['width']))
            files_info.append({
                'file_name': file_name,
                'size': max_size['type'],
                'url': max_size['url']
            })

        with open('photos_info.json', 'w') as json_file:
            json.dump(files_info, json_file)

        return files_info


def main():
    vk_id = input('Your VK ID or nickname: ')
    ya_token = input('Your Yandex token: ')
    try:
        quantity = int(input('Number of photos: '))
    except ValueError:
        logging.error('The value must be an integer!')
        return

    vk_api = VKApi(vk_id)
    photos = vk_api.get_photos(quantity)

    if photos:
        files_info = PhotoManager.create_json_file(photos)
        ya_disk = YaDisk(ya_token)
        ya_disk.put_photo(files_info)


if __name__ == "__main__":
    main()
