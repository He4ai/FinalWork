import requests
import datetime
import json
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Vk:

    access_token = ('vk1.a.pGc7PQy5EehT6GeHxiUFM1f1roNHT'
                    'ppLMowo-k9w3ageBxbVIRETgATREj4KpQUYl'
                    'clGYRgW-fJ9dqppmaqJOQUOKk8Fw46MCimZBy'
                    'Owvdfh3EpgqJbngDANXbSQ5WRvkUvHOnj8Yj8p'
                    'lxpPmw-FEPcbDRl4nCWyTRstXiKH8kRSFc_GV7kij26mkJTfNOyW')  # токен полученный из инструкции

    def __init__(self, vk_id, ya_token, version='5.131'):
        self.vk_id = vk_id
        self.ya_token = 'OAuth ' + ya_token
        self.version = version
        self.params = {'access_token': self.access_token,
                       'v': self.version}

    # Ф-ия для создания папки Vk Photo на я.диске
    def _create_folder(self):
        url = 'https://cloud-api.yandex.net/v1/disk/resources'
        params = {'path': 'VK Photos'}
        headers = {'Authorization': self.ya_token}
        response = requests.put(url, params=params, headers=headers)

    # Ф-ия для взятия фото из вк
    def _get_photos(self, quantity):
        url = 'https://api.vk.com/method/photos.get'
        params = {'owner_id': self.vk_id,
                  'extended': 1,
                  'album_id': 'profile',
                  'count': quantity}
        response = requests.get(url, params={**self.params, **params})
        try:
            if response.json()['response']['count'] == 0:  # Проверка на то, есть ли фото вообще
                return
            else:  # Проверка на случай, если указано больше фото, чем есть у пользователя
                if response.json()['response']['count'] < quantity:
                    logging.info('The user has fewer photos than you specified. '
                          f'Only {response.json()["response"]["count"]} photos will be uploaded.')
                all_photos = response.json()['response']['items']
        except KeyError:
            return
        else:
            return self._create_json_file(all_photos)  # Вызов функции для формирования json файла

    @staticmethod  # Ф-ия для формирования json файла
    def _create_json_file(all_photos):
        files_info = []  # Массив со всеми словарями
        file_names = []  # Массив с именами для проверки на совпадения

        for photo_data in all_photos:
            file_name = f"{photo_data['likes']['count']}.jpg"
            date_str = str(datetime.datetime.fromtimestamp(photo_data["date"])).split()[0]
            if file_name in file_names:  # Проверка на совпадение имени
                index = file_names.index(file_name)
                file_names[index] = (f'{file_names[index][:-4]} '  # Меняем оба имени, добавляя к ним дату
                                     f'{str(datetime.datetime.fromtimestamp(all_photos[index]["date"])).split()[0]}'
                                     '.jpg')
                files_info[index]['file_name'] = file_names[index]
                file_name = f"{file_name[:-4]} {date_str}.jpg"
            file_names.append(file_name)

            # В файл сохраняем только информацию о самом большом формате
            max_size = max(photo_data['sizes'], key=lambda x: (x['height'], x['width']))
            files_info.append({
                'file_name': file_name,
                'size': max_size['type'],
                'url': max_size['url']
            })

            with open('photos_info.json', 'w') as json_file:  # Запись в файл
                json.dump(files_info, json_file)

        return files_info

    # Ф-ия для загрузки фото на я.диск
    def put_photo(self, quantity=5):
        self._create_folder()  # Создание папки
        logging.info(f'Folder created successfully')
        url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        headers = {'Authorization': self.ya_token}
        all_photos = self._get_photos(quantity)  # Выгрузка информации о фото + формирование json-файла
        if not all_photos:  # Проверка на наличие фото
            print('The user does not have a photo or you entered the wrong ID!')
        else:
            logging.info(f'Photos successfully found')
            for photo in tqdm(all_photos, desc='Uploading photos', unit='photo'):  # Логирование д-ий программы
                while True:  # Цикл для проверки имён файлов
                    try:
                        params = {'path': f'VK Photos/{photo["file_name"]}',
                                  'overwrite': False}
                        response = requests.get(url, params=params, headers=headers)
                        url_upload = response.json()['href']
                        file_response = requests.get(photo['url'])
                        response = requests.put(url_upload, headers=headers, data=file_response.content)
                        logging.info(f'Successfully uploaded {photo["file_name"]}')
                        break
                    except KeyError:
                        # Смена имени если такой файл уже есть на диске
                        if response.json()['error'] == 'DiskResourceAlreadyExistsError':
                            if '(' not in photo["file_name"]:
                                photo["file_name"] = f'{photo["file_name"][:-4]}(1).jpg'
                            else:
                                photo["file_name"] = (f'{photo["file_name"][:-6]}'
                                                      f'{int(photo["file_name"][-6]) + 1}'
                                                      f').jpg')
                        # На случай неверного я.токена
                        elif response.json()['error'] == 'UnauthorizedError':
                            logging.error(f'Invalid Yandex token')
                            break


user_id = input('Введите идентификатор пользователя ВК')
yandex_token = input('Введите ваш яндекс-токен')
vk_user = Vk(user_id, yandex_token)
vk_user.put_photo(3)
