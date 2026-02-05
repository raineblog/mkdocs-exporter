import yaml
import json
from pathlib import Path

script_dir = Path(__file__).parent.resolve()

def parse_yaml(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as file:
        text = file.read()
    return yaml.load(text, Loader=yaml.FullLoader)

def extract_title(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if line.startswith('# '):
                return line[2:].strip()
    return "无标题"

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def write_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def get_site_nav(nav):
    return [{item['title']: item['children']} for item in nav]
