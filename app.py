# ┌───────────────────────────────────────────
# │  KK_ExternalVoiceEditor v1.0.0 (2025.06.01)
# └───────────────────────────────────────────
# ==============================================================================
# pip install gradio
# pip install pandas

import gradio as gr
import locale
import sqlite3
import pandas as pd
import random
import string
import json
import os
import re
import winreg
import tempfile
import zipfile
import subprocess
import shutil
from pathlib import Path
# ==============================================================================
# JSON形式パース
def parse_json(json_data, result=None, key_prefix=""):
	if result is None:
		result = {}

	for key, value in json_data.items():
		new_key = f"{key_prefix}.{key}" if key_prefix else key

		if isinstance(value, dict):
			parse_json(value, result, key_prefix=new_key)
		else:
			result[new_key] = value

	return result

# ------------------------------------------------------------------------------
# データベースから全レコードを取得
def get_records():
	global df_model, df_character

	# None の場合はワイルドカード
	model = df_model or "%"
	character = df_character or "%"

	# Gradioコンポーネントが dict の場合に対応
	if isinstance(model, dict):
		model = model.get("value") or model.get("label") or "%"
	if isinstance(character, dict):
		character = character.get("value") or character.get("label") or "%"

	# 文字列化（念のため）
	model = str(model)
	character = str(character)

	conn = sqlite3.connect(conf['db_path'])
	df = pd.read_sql_query(f"""
		SELECT
			model.name || '(' || model.description || ')' AS model, 
			voice.id, 
			'c' || character.id || ' ' || character.name AS character, 
			category.name AS category, 
			voice.words, 
			voice.path, 
			voice.file 
		FROM {conf['tbl_voice']} AS voice
		LEFT JOIN {conf['tbl_model']} AS model
			ON voice.model = model.id
		LEFT JOIN {conf['tbl_character']} AS character
			ON voice.character = character.id
		LEFT JOIN {conf['tbl_category']} AS category
			ON voice.category = category.id
		WHERE model.id LIKE ? AND character.id LIKE ?
		ORDER BY voice.sort
	""", conn, params=(model, character))
	conn.close()
	return df



# ------------------------------------------------------------------------------
# 指定したIDのレコードを取得
def get_record(id):
	with sqlite3.connect(conf['db_path']) as conn:
		cursor = conn.cursor()
		cursor.execute(f"""
			SELECT 
			model.name || '(' || model.description || ')' AS model, 
			voice.id, 
			voice.character, 
			voice.category, 
			voice.words, 
			voice.path, 
			voice.file 
			FROM {conf['tbl_voice']} 
			LEFT JOIN {conf['tbl_model']} 
			ON voice.model = model.id 
			WHERE voice.id = '{id}'
		""")
		result = cursor.fetchone()
	if result:
		return result[0], result[1], result[2], result[3], result[4], result[5], result[6]
	else:
		return None, None, None, None, None, None, None

# ------------------------------------------------------------------------------
# キャッシュ取得
def get_cache(tab, field):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"SELECT value FROM {conf['tbl_gradio']} WHERE tab = ? AND field = ?", (tab, field))
	result = cursor.fetchone()
	conn.close()
	return result[0]

# ------------------------------------------------------------------------------
# キャッシュ変更
def update_cache(tab, field, value):
	# JSON文字列化（日本語OK）
	value_str = json.dumps(value, ensure_ascii=False)
	# 文字列の両端のダブルクォートを削除
	if isinstance(value, str):
		value_str = value_str.strip('"')

	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"UPDATE {conf['tbl_gradio']} SET value = ? WHERE tab = ? AND field = ?", (value_str, tab, field))
	conn.commit()
	conn.close()

# ------------------------------------------------------------------------------
# 最大 sort を返す関数
def get_new_sort():
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"SELECT MAX(sort) FROM {conf['tbl_voice']}")
	result = cursor.fetchone()
	conn.close()
	return (result[0]+1) if result[0] is not None else 0

# ------------------------------------------------------------------------------
# ランダム文字列生成
def generate_random_id(length=8):
	chars = string.ascii_letters + string.digits  # 英大文字・小文字 + 数字
	return ''.join(random.choices(chars, k=length))

# ------------------------------------------------------------------------------
# ID存在チェック
def id_exists(voice_id: str) -> bool:
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute("SELECT 1 FROM voice WHERE id = ?", (voice_id,))
	result = cursor.fetchone()
	conn.close()
	return result is not None

# ------------------------------------------------------------------------------
# ユニークなIDを生成
def generate_unique_id(length=8):
	while True:
		new_id = generate_random_id(length)
		if not id_exists(new_id):
			return new_id

# ------------------------------------------------------------------------------
# 言語別メッセージ取得
def get_message(target, id, cd, **kwargs):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute("SELECT value FROM language WHERE target = ? AND id = ? AND cd = ?", (target, id, cd))
	template = cursor.fetchone()[0]
	return template.format(**kwargs)

# ------------------------------------------------------------------------------
# 言語別メッセージ群取得
def get_messages(target, cd):
	conn = sqlite3.connect(conf['db_path'])
	df = pd.read_sql_query(f"SELECT id, value FROM language WHERE target = '{target}' AND cd = '{cd}'", conn)
	conn.close()
	return df

# ------------------------------------------------------------------------------
# ボイス言語変更
def change_voice_language(id, words):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"UPDATE voice SET words = ? WHERE id = ?", (words, id))
	conn.commit()
	conn.close()

# ------------------------------------------------------------------------------
# 性格言語変更
def change_character_language(id, name):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"UPDATE character SET name = ? WHERE id = ?", (name, id))
	conn.commit()
	conn.close()

# ------------------------------------------------------------------------------
# カテゴリー言語変更
def change_category_language(id, name):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"UPDATE category SET name = ? WHERE id = ?", (name, id))
	conn.commit()
	conn.close()

# ------------------------------------------------------------------------------
# モデル言語変更
def change_model_language(id, name, description):
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()
	cursor.execute(f"UPDATE model SET name = ?, description = ? WHERE id = ?", (name, description, id))
	conn.commit()
	conn.close()

# ------------------------------------------------------------------------------
# 言語変更

def change_language(language_dropdown, list_model_dropdown, list_character_dropdown, character_dropdown, category_dropdown):

	global kk_path, kks_path, kkp_path
	global language
	if language == language_dropdown: 
		components = [
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update(), 
			gr.update() 
		]

		# kk_button 系を条件付きで追加
		if kk_path is not None:
			components.append(gr.update())
		if kks_path is not None:
			components.append(gr.update())
		if kkp_path is not None:
			components.append(gr.update())
		return components
	else: 
		update_cache("default", "language", language_dropdown)
		language = language_dropdown

	# データベース変更
	conn = sqlite3.connect(conf['db_path'])
	cursor = conn.cursor()

	# ボイスレコード言語切替
	voices = get_messages("voice", language)
	for index, row in voices.iterrows():
		cursor.execute(f"UPDATE voice SET words = ? WHERE id = ?", (row["value"], row["id"]))

	# 性格レコード言語切替
	characters = get_messages("character", language)
	for index, row in characters.iterrows():
		cursor.execute(f"UPDATE character SET name = ? WHERE id = ?", (row["value"], row["id"]))

	# カテゴリーレコード言語切替
	categories = get_messages("category", language)
	for index, row in categories.iterrows():
		cursor.execute(f"UPDATE category SET name = ? WHERE id = ?", (row["value"], row["id"]))

	# モデルレコード言語切替
	models = get_messages("model", language)
	for index, row in models.iterrows():
		name, description = row["value"].split(",", 1)
		cursor.execute(f"UPDATE model SET name = ?, description = ? WHERE id = ?", (name, description, row["id"]))

	conn.commit()
	conn.close()

	# ドロップダウン取得
	list_model_options, list_character_options, character_options, category_options = get_dropdown_options()

	game_options = [(get_message('inference', 'radio_target_path', language), "0")]
	if kk_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatu', language), "1"))
	if kks_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatsu_sunshine', language), "2"))
	if kkp_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatsu_party', language), "3"))

	components = [
		gr.update(value=f"# {get_message('inference', 'label_title', language)}"), 
		gr.update(label=get_message('inference', 'label_model', language), choices=list_model_options, value=list_model_dropdown), 
		gr.update(label=get_message('inference', 'label_character', language), choices=list_character_options, value=list_character_dropdown), 
		gr.update(value=get_message('inference', 'button_reload', language)), 
		gr.update(value=get_records(), label=get_message('inference', 'label_voice_list', language)), 
		gr.update(value=f"## {get_message('inference', 'label_edit', language)}"), 
		gr.update(value=get_message('inference', 'button_add', language)), 
		gr.update(value=get_message('inference', 'button_change', language)), 
		gr.update(value=get_message('inference', 'button_delete', language)), 
		gr.update(label=get_message('inference', 'label_model_not_editable', language)), 
		gr.update(label=get_message('inference', 'label_id_not_editable', language)), 
		gr.update(label=get_message('inference', 'label_character', language), choices=character_options, value=character_dropdown), 
		gr.update(label=get_message('inference', 'label_category', language), choices=category_options, value=category_dropdown), 
		gr.update(label=get_message('inference', 'label_lines', language)), 
		gr.update(label=get_message('inference', 'label_path', language)), 
		gr.update(label=get_message('inference', 'label_filename', language)), 
		gr.update(label=get_message('inference', 'label_output_path', language)), 
		gr.update(label=get_message('inference', 'label_output_destination', language), choices=game_options), 
		gr.update(value=get_message('inference', 'button_output_start', language)), 
		gr.update(label=get_message('inference', 'label_message', language))
	]

	# kk_button 系を条件付きで追加
	if kk_path is not None:
		components.append(gr.update(value=get_message('inference', 'button_start_koikatu', language)))
	if kks_path is not None:
		components.append(gr.update(value=get_message('inference', 'button_start_koikatsu_sunshine', language)))
	if kkp_path is not None:
		components.append(gr.update(value=get_message('inference', 'button_start_koikatsu_party', language)))

	return tuple(components)

# ------------------------------------------------------------------------------
# パス有効チェック
def is_invalid_windows_path(path: str) -> bool:
	# 最大パス長（Windowsの制限）
	if len(path) > 260:
		return True

	# 禁止文字チェック（コロンは特別扱い）
	if re.search(r'[<>\"|?*]', path):
		return True

	# コロンが "C:" のように 2文字目以外にある場合は無効
	colon_matches = list(re.finditer(r':', path))
	if colon_matches:
		for m in colon_matches:
			if m.start() != 1:	# "C:" のような形式でない
				return True

	# パスの各パーツを予約名と照合
	reserved_names = {
		'CON', 'PRN', 'AUX', 'NUL',
		*(f'COM{i}' for i in range(1, 10)),
		*(f'LPT{i}' for i in range(1, 10)),
	}

	parts = re.split(r'[\\/]', path)
	for part in parts:
		if not part or part in {'.', '..'}:
			continue
		name = part.split('.')[0].upper()
		if name in reserved_names:
			return True

	return False

# ------------------------------------------------------------------------------
# ドロップダウン
def get_dropdown_options():
	with sqlite3.connect(conf['db_path']) as conn:
		model_df = pd.read_sql_query(f"SELECT id, name || '(' || description || ')' AS view FROM {conf['tbl_model']}", conn)
		character_df = pd.read_sql_query(f"SELECT id, 'c' || id || ' ' || name AS view FROM {conf['tbl_character']}", conn)
		category_df  = pd.read_sql_query(f"SELECT id, name FROM {conf['tbl_category']}",  conn)

	list_model_options     = [("", "%")] + [(row["view"], row["id"]) for _, row in model_df.iterrows()]
	list_character_options = [("", "%")] + [(row["view"], row["id"]) for _, row in character_df.iterrows()]
	character_options = [(row["view"], row["id"]) for _, row in character_df.iterrows()]
	category_options  = [(row["name"], row["id"]) for _, row in category_df.iterrows()]
	return list_model_options, list_character_options, character_options, category_options

# ------------------------------------------------------------------------------
# レコード追加
def add_record(character, category, words, path, file):

	if not words:
		return (
			get_message('inference', 'message_error_words', language), 
			get_records(), 
			None, 
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False)
		)
	elif not path:
		return (
			get_message('inference', 'message_error_path', language), 
			get_records(), 
			None, 
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False)
		)
	elif not file:
		return (
			get_message('inference', 'message_error_file', language), 
			get_records(), 
			None, 
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False)
		)

	new_id = generate_unique_id()

	try:
		conn = sqlite3.connect(conf['db_path'])
		cursor = conn.cursor()
		cursor.execute(
			f"INSERT INTO {conf['tbl_voice']} (model, id, sort, character, category, words, path, file) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
			("0000", new_id, get_new_sort(), character, category, words, path, file)
		)
		conn.commit()
		conn.close()
		return (
			get_message('inference', 'message_success_add', language), 
			get_records(), 
			new_id, 
			*update_move_button(new_id)
		)

	except Exception as e:
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			new_id, 
			*update_move_button(new_id)
		)

# ------------------------------------------------------------------------------
# レコード変更
def update_record(id, character, category, words, path, file):

	if not words:
		return (
			get_message('inference', 'message_error_words', language), 
			get_records(), 
			*update_move_button(id)
		)
	elif not path:
		return (
			get_message('inference', 'message_error_path', language), 
			get_records(), 
			*update_move_button(id)
		)
	elif not file:
		return (
			get_message('inference', 'message_error_file', language), 
			get_records(), 
			*update_move_button(id)
		)

	try:
		conn = sqlite3.connect(conf['db_path'])
		cursor = conn.cursor()
		cursor.execute(
			f"UPDATE {conf['tbl_voice']} SET character = ?, category = ?, words = ?, path = ?, file = ? WHERE id = ?", 
			(character, category, words, path, file, id)
		)
		conn.commit()
		conn.close()
		return (
			get_message('inference', 'message_success_change', language), 
			get_records(), 
			*update_move_button(id)
		)

	except Exception as e:
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			*update_move_button(id)
		)

# ------------------------------------------------------------------------------
# レコード削除
def delete_record(id):

	if not id:
		return (
			get_message('inference', 'message_error_id', language), 
			get_records(), 
			*update_move_button(id), 
			*get_record(id) 
		)
	try:
		conn = sqlite3.connect(conf['db_path'])
		cursor = conn.cursor()
		cursor.execute(f"DELETE FROM {conf['tbl_voice']} WHERE id = ?", (id,))
		conn.commit()
		conn.close()
		return (
			get_message('inference', 'message_success_delete', language), 
			get_records(), 
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False),
			gr.update(interactive=False),
			None, None, None, None, None, None, None 
		)

	except Exception as e:
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			*update_move_button(id), 
			*get_record(id) 
		)

# ------------------------------------------------------------------------------
# 選択したレコードのデータをフォームにセット
def select_record(evt: gr.SelectData):
	df = get_records()
	selected_id = df.iloc[evt.index[0]]['id']
	update_move_button(selected_id)
	return (
		*update_move_button(selected_id),
		*get_record(selected_id) 
	)

# ------------------------------------------------------------------------------
# フィールド変更
def update_list_model(model):
	update_cache("list", "list_model_dropdown", model)
	global df_model
	df_model = model

def update_list_character(character):
	update_cache("list", "list_character_dropdown", character)
	global df_character
	df_character = character

def update_model(model):
	update_cache("list", "model_input", model)

def update_id(id):
	update_cache("list", "id_input", id)

def update_character(character):
	update_cache("list", "character_dropdown", character)

def update_category(category):
	update_cache("list", "category_dropdown", category)

def update_words(words):
	update_cache("list", "words_input", words)

def update_path(path):
	update_cache("list", "path_input", path)

def update_file(file):
	update_cache("list", "file_input", file)

def update_voice(voice):
	update_cache("list", "voice_player", voice)

def update_path_file(path, file):
	update_path(path)
	update_file(file)
	voice = conf['voice_path']+'/'+path+'/'+file
	update_voice(voice)
	if os.path.exists(voice) and voice.lower().endswith('.wav'):
		return gr.update(value=voice)
	else:
		return gr.update(value=None)

# ------------------------------------------------------------------------------
# 移動ボタン切替
def update_move_button(target_id):
	df = get_records()
	ids = df["id"].tolist()
	if target_id is None or target_id not in ids:
		return (gr.update(interactive=False),) * 4	# 全部非活性にする

	idx = ids.index(target_id)
	global first_id, prev_id, next_id, last_id

	first_id = ids[0]  if ids else None
	prev_id  = ids[idx - 1] if idx > 0 else None
	next_id  = ids[idx + 1] if idx < len(ids) - 1 else None
	last_id  = ids[-1] if ids else None

	return (
		gr.update(interactive=(target_id != first_id)), 
		gr.update(interactive=(prev_id is not None)), 
		gr.update(interactive=(next_id is not None)), 
		gr.update(interactive=(target_id != last_id)) 
	)

def move_first(target_id):
	return move_sort_to_top(target_id)

def move_prev(target_id):
	return swap_sort_values(target_id, prev_id)

def move_next(target_id):
	return swap_sort_values(target_id, next_id)

def move_last(target_id):
	return move_sort_to_bottom(target_id)

# ------------------------------------------------------------------------------
# レコード移動
def swap_sort_values(id1, id2):
	conn = sqlite3.connect(conf['db_path'])
	try:
		cursor = conn.cursor()
		# それぞれの id に対応する sort 値を取得
		cursor.execute(f"SELECT sort FROM {conf['tbl_voice']} WHERE id = ?", (id1,))
		result1 = cursor.fetchone()
		if result1 is None:
			raise ValueError(get_message('inference', 'message_not_found_id', language, target=id1))

		cursor.execute(f"SELECT sort FROM {conf['tbl_voice']} WHERE id = ?", (id2,))
		result2 = cursor.fetchone()
		if result2 is None:
			raise ValueError(get_message('inference', 'message_not_found_id', language, target=id2))

		sort1 = result1[0]
		sort2 = result2[0]

		# トランザクション開始
		conn.execute("BEGIN")

		# sort 値を入れ替える
		cursor.execute(f"UPDATE {conf['tbl_voice']} SET sort = ? WHERE id = ?", (sort2, id1))
		cursor.execute(f"UPDATE {conf['tbl_voice']} SET sort = ? WHERE id = ?", (sort1, id2))

		# コミット
		conn.commit()
		return (
			get_message('inference', 'message_success_move', language), 
			get_records(), 
			*update_move_button(id1)
		)

	except Exception as e:
		conn.rollback()
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			*update_move_button(id1)
		)

	finally:
		conn.close()

# ------------------------------------------------------------------------------
# 最上位移動
def move_sort_to_top(target_id):
	conn = sqlite3.connect(conf['db_path'])
	try:
		cursor = conn.cursor()

		# 対象レコードの元の sort を取得
		cursor.execute("SELECT sort FROM voice WHERE id = ?", (target_id,))
		result = cursor.fetchone()
		if result is None:
			raise ValueError(get_message('inference', 'message_not_found_id', language, target=target_id))

		original_sort = result[0]

		# トランザクション開始
		conn.execute("BEGIN")

		# 元のsortより小さいすべてのレコードのsortを+1
		cursor.execute("""
			UPDATE voice
			SET sort = sort + 1
			WHERE sort < ?
		""", (original_sort,))

		# 対象レコードのsortを0に設定
		cursor.execute("UPDATE voice SET sort = 0 WHERE id = ?", (target_id,))

		conn.commit()
		return (
			get_message('inference', 'message_success_move', language), 
			get_records(), 
			*update_move_button(target_id)
		)

	except Exception as e:
		conn.rollback()
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			*update_move_button(target_id)
		)

	finally:
		conn.close()

# ------------------------------------------------------------------------------
# 最下位移動
def move_sort_to_bottom(target_id):
	conn = sqlite3.connect(conf['db_path'])
	try:
		cursor = conn.cursor()
		# 対象レコードの元の sort を取得
		cursor.execute("SELECT sort FROM voice WHERE id = ?", (target_id,))
		result = cursor.fetchone()
		if result is None:
			raise ValueError(get_message('inference', 'message_not_found_id', language, target=target_id))
		original_sort = result[0]

		# 最大 sort を取得（対象レコードを除く）
		cursor.execute("SELECT MAX(sort) FROM voice WHERE id != ?", (target_id,))
		max_sort = cursor.fetchone()[0]
		new_sort = max_sort + 1 if max_sort is not None else 0

		# トランザクション開始
		conn.execute("BEGIN")

		# 元のsort以上の他のレコードのsortを -1（自身は除外）
		cursor.execute("""
			UPDATE voice
			SET sort = sort - 1
			WHERE sort > ? AND id != ?
		""", (original_sort, target_id))

		# 対象レコードのsortを最大に更新
		cursor.execute("UPDATE voice SET sort = ? WHERE id = ?", (new_sort, target_id))

		conn.commit()
		return (
			get_message('inference', 'message_success_move', language), 
			get_records(), 
			*update_move_button(target_id)
		)
	except Exception as e:
		conn.rollback()
		return (
			get_message('inference', 'message_error', language, error=str(e)), 
			get_records(), 
			*update_move_button(target_id)
		)

	finally:
		conn.close()

# ------------------------------------------------------------------------------
# レジストリ取得
def read_registry_value(root, path, name):
	try:
		with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
			value, regtype = winreg.QueryValueEx(key, name)
			return value
	except FileNotFoundError:
		return None

def get_output_value():
	global kk_path, kks_path
	game = get_cache("list", "game_radio")

	# キャッシュの出力先がアンインストールして無くなっていた場合
	if (game == "1" and kk_path is None) or (game == "2" and kks_path is None):
		game = "0"

	if game == "0":
		return get_cache("list", "output_input")
	elif game == "1":
		return kk_path
	elif game == "2":
		return kks_path

def get_output_interactive():
	global kk_path, kks_path
	game = get_cache("list", "game_radio")

	# キャッシュの出力先がアンインストールして無くなっていた場合
	if (game == "1" and kk_path is None) or (game == "2" and kks_path is None):
		game = "0"

	if game == "0":
		return True
	else:
		return False

def update_output(output, game):
	if game == "0":
		update_cache("list", "output_input", output)

def select_game(game):
	update_cache("list", "game_radio", game)
	if game == "0":
		return gr.update(value=get_cache("list", "output_input"), interactive=True)
	elif game == "1":
		return gr.update(value=kk_path, interactive=False)
	elif game == "2":
		return gr.update(value=kks_path, interactive=False)

def kk_run():
	global kk_path
	exe_path = os.path.join(kk_path, "InitSetting.exe")
	subprocess.run([exe_path])

def kks_run():
	global kks_path
	exe_path = os.path.join(kks_path, "InitSetting.exe")
	subprocess.run([exe_path])

def kkp_run():
	global kkp_path
	exe_path = os.path.join(kkp_path, "Initial Settings.exe")
	subprocess.run([exe_path])

# ------------------------------------------------------------------------------
# 出力
def output_contents(output, game):

	if output != "" and is_invalid_windows_path(output):
		return (get_message('inference', 'message_invalid_output_path', language, output=output))

	current_path = os.getcwd()

	if os.path.isabs(output):
		target_path = output
	else:
		# 相対パスなら絶対パスに
		target_path = os.path.join(current_path, output)

	# outputが空でなく、カレントディレクトリと同義
	path_curren = Path(current_path)
	path_target = Path(target_path)
	if output != "" and path_curren.resolve(strict=False) == path_target.resolve(strict=False):
		output = ""
		target_path = current_path

	os.makedirs(target_path, exist_ok=True)

	#temp_path    = os.path.join(current_path, 'temp')
	#os.makedirs(temp_path, exist_ok=True)

	# テンポラリフォルダ
	with tempfile.TemporaryDirectory() as temp_path:

		# ----------------------------------------------------------------------
		# manifest.xml出力
		manifest_path = os.path.join(temp_path, conf['mod_manifest_file'])

		with open(manifest_path, "w", encoding="utf-8") as f:
			f.write(conf['mod_manifest'].format(
				mod_guid        = conf['mod_guid'], 
				mod_name        = conf['mod_name'], 
				mod_version     = conf['mod_version'], 
				mod_author      = conf['mod_author'], 
				mod_description = conf['mod_description'], 
				mod_website     = conf['mod_website']
			))

		# ----------------------------------------------------------------------
		# csv出力
		csv_path = os.path.join(
			temp_path, 
			conf['mod_voice_list_path'].format(mod_name = conf['mod_name'], mod_version = conf['mod_version'])
		)
		os.makedirs(csv_path, exist_ok=True)

		conn = sqlite3.connect(conf['db_path'])
		cursor = conn.cursor()

		# 性格情報取得
		cursor.execute("SELECT * FROM character")
		character_rows = cursor.fetchall()

		# カテゴリー情報取得
		cursor.execute("SELECT * FROM category")
		category_rows = cursor.fetchall()

		# カテゴリーcsv出力
		for character_row in character_rows:
			category_path = os.path.join(csv_path, conf['voice_category_file'].format(character = character_row[0]))

			with open(category_path, "w", encoding="utf-8") as category_f:
				category_f.write(conf['voice_category_header'])

				for category_row in category_rows:
					category_f.write(f"{category_row[0]},{category_row[1]}\n")

					# ボイスリストcsv出力
					cursor.execute(f"SELECT character, category, words, path, file FROM voice WHERE character = '{character_row[0]}' AND category = '{category_row[0]}' ORDER BY sort")
					voice_list_rows = cursor.fetchall()

					voice_list_path = os.path.join(
						csv_path, 
						conf['voice_list_file'].format(character = character_row[0], category = category_row[0])
					)
					with open(voice_list_path, "w", encoding="utf-8") as voice_list_f:
						voice_list_f.write(conf['voice_list_header'])

						num = 0
						for voice_list_row in voice_list_rows:
							voice_list_f.write(f"{num},{voice_list_row[0]},{voice_list_row[1]},{voice_list_row[2]},{voice_list_row[3]},{voice_list_row[4]}\n")
							num += 1

		# ----------------------------------------------------------------------
		# zipmod出力
		mod_path = os.path.join(target_path, conf['mod_path'])
		os.makedirs(mod_path, exist_ok=True)
		mod_file_path = os.path.join(
			mod_path, conf['mod_file'].format(mod_name = conf['mod_name'], mod_version = conf['mod_version'])
		)

		with zipfile.ZipFile(mod_file_path, 'w') as zip_f:
			zip_f.write(manifest_path, arcname=conf['mod_manifest_file'])

			for character_row in character_rows:
				category_path = os.path.join(csv_path, conf['voice_category_file'].format(character = character_row[0]))

				character_arcname_path = os.path.join(
					conf['mod_voice_list_path'].format(mod_name = conf['mod_name'], mod_version = conf['mod_version']), 
					conf['voice_category_file'].format(character = character_row[0])
				)
				zip_f.write(category_path, arcname=character_arcname_path)

				for category_row in category_rows:

					voice_list_path = os.path.join(
						csv_path, 
						conf['voice_list_file'].format(character = character_row[0], category = category_row[0])
					)

					voice_arcname_path = os.path.join(
						conf['mod_voice_list_path'].format(mod_name = conf['mod_name'], mod_version = conf['mod_version']), 
						conf['voice_list_file'].format(character = character_row[0], category = category_row[0])
					)
					zip_f.write(voice_list_path, arcname=voice_arcname_path)

	# --------------------------------------------------------------------------
	# カレントディレクトリでないなら
	path_curren = Path(current_path)
	path_target = Path(target_path)
	if path_curren.resolve(strict=False) != path_target.resolve(strict=False):
		# ----------------------------------------------------------------------
		# ボイスデータコピー
		userdata_path = os.path.join(current_path, conf['voice_path'])
		target_userdata_path = os.path.join(target_path, conf['voice_path'])

		cursor.execute(f"SELECT character, category, words, path, file FROM voice ORDER BY sort")
		voice_list_rows = cursor.fetchall()

		for voice_list_row in voice_list_rows:
			voice_path = os.path.join(userdata_path, f"{voice_list_row[3]}/{voice_list_row[4]}")
			if os.path.isfile(voice_path):
				target_voice_path = os.path.join(target_userdata_path, f"{voice_list_row[3]}/{voice_list_row[4]}")
				os.makedirs(os.path.dirname(target_voice_path), exist_ok=True)
				shutil.copy(voice_path, target_voice_path)

		# ----------------------------------------------------------------------
		# プラグインコピー
		global kk_path, kks_path

		path_kk  = Path(kk_path)
		path_kks = Path(kks_path)

		if (
			path_kk.resolve(strict=False) == path_target.resolve(strict=False) or 
			path_kks.resolve(strict=False) == path_target.resolve(strict=False)
		):

			# コイカツの場合
			if path_kk.resolve(strict=False) == path_target.resolve(strict=False):
				plugin_path = os.path.join(current_path, f"{conf['plugin_path']}/{conf['plugin_kk_file']}")
				target_plugin_path = os.path.join(kk_path, f"{conf['plugin_path']}/{conf['plugin_kk_file']}")

			# コイカツサンシャインの場合
			elif path_kks.resolve(strict=False) == path_target.resolve(strict=False):
				plugin_path = os.path.join(current_path, f"{conf['plugin_path']}/{conf['plugin_kks_file']}")
				target_plugin_path = os.path.join(kks_path, f"{conf['plugin_path']}/{conf['plugin_kks_file']}")

			os.makedirs(os.path.dirname(target_plugin_path), exist_ok=True)
			shutil.copy(plugin_path, target_plugin_path)

	conn.close()
	return (get_message('inference', 'message_completed_output', language))

# ------------------------------------------------------------------------------
# Gradioインターフェース
def create_interface():

	# 言語
	global language
	language = get_cache("default", "language")
	if language is None:
		language = locale.getdefaultlocale()[0][:2]
		update_cache("default", "language", language)

	# 一覧フィルター
	global df_model, df_character
	df_model     = None
	df_character = None

	df_model     = get_cache("list", "list_model_dropdown")
	df_character = get_cache("list", "list_character_dropdown")

	# ドロップダウン取得
	list_model_options, list_character_options, character_options, category_options = get_dropdown_options()

	# インストールパス取得
	global kk_path, kks_path, kkp_path
	kk_path  = read_registry_value(winreg.HKEY_CURRENT_USER, conf['registry_kk' ], "INSTALLDIR")
	kks_path = read_registry_value(winreg.HKEY_CURRENT_USER, conf['registry_kks'], "INSTALLDIR")
	kkp_path = read_registry_value(winreg.HKEY_CURRENT_USER, conf['registry_kkp'], "INSTALLDIR")

	global game_options
	game_options = [(get_message('inference', 'radio_target_path', language), "0")]
	if kk_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatu', language), "1"))
	if kks_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatsu_sunshine', language), "2"))
	if kkp_path is not None:
		game_options.append((get_message('inference', 'radio_target_koikatsu_party', language), "3"))


	# --------------------------------------------------------------------------
	with gr.Blocks(theme='NoCrypt/miku') as demo:
		gr.HTML("""
			<style>
				#List {
					.cell-selected>div>button {display:none;}
					tr:has(td.cell-selected){background-color: var(--color-accent);}
				}
				#Model textarea:disabled, 
				#Id textarea:disabled, 
				#Output textarea:disabled{opacity: 0.3;}
				.lang-row {
					justify-content: space-between !important; /* 左右に分ける */
					align-items: center;
				}
				#language_dropdown {width: 150px !important;}
			</style>
		""")
		with gr.Row(elem_classes="lang-row"):
			title_markdown = gr.Markdown(f"# {get_message('inference', 'label_title', language)}")

			# 言語
			language_dropdown = gr.Dropdown(
				choices=[("日本語", "ja"), ("English", "en")], 
				value=language, 
				label="Language / 言語"
			)

		# レコード一覧
		with gr.Row():
			list_model_dropdown      = gr.Dropdown(label=get_message('inference', 'label_model', language), choices=list_model_options, value=df_model, allow_custom_value=True)
			list_character_dropdown  = gr.Dropdown(label=get_message('inference', 'label_character', language), choices=list_character_options, value=df_character, allow_custom_value=True)
		with gr.Row():
			df_reload_button = gr.Button(get_message('inference', 'button_reload', language))
		with gr.Row():
			df_output = gr.Dataframe(value=get_records, interactive=False, label=get_message('inference', 'label_voice_list', language), elem_id="List")

		# フォーム
		with gr.Row():
			with gr.Column():
				edit_markdown = gr.Markdown(f"## {get_message('inference', 'label_edit', language)}")
				with gr.Row():
					first_button = gr.Button("△", elem_id="First")
					prev_button  = gr.Button("▲", elem_id="Prev")
					next_button  = gr.Button("▼", elem_id="Next")
					last_button  = gr.Button("▽", elem_id="Last")

				with gr.Row():
					add_button    = gr.Button(get_message('inference', 'button_add', language))
					update_button = gr.Button(get_message('inference', 'button_change', language))
					delete_button = gr.Button(get_message('inference', 'button_delete', language))

				model_input = gr.Textbox(label=get_message('inference', 'label_model_not_editable', language), interactive=False, elem_id="Model", value=get_cache("list", "model_input"))
				id_input    = gr.Textbox(label=get_message('inference', 'label_id_not_editable', language), interactive=False, elem_id="Id", value=get_cache("list", "id_input"))
				character_dropdown = gr.Dropdown(label=get_message('inference', 'label_character', language), choices=character_options, value=get_cache("list", "character_dropdown"), allow_custom_value=True)
				category_dropdown  = gr.Dropdown(label=get_message('inference', 'label_category', language), choices=category_options, value=get_cache("list", "category_dropdown"), allow_custom_value=True)
				words_input = gr.Textbox(label=get_message('inference', 'label_lines', language), value=get_cache("list", "words_input"))
				path_input  = gr.Textbox(label=get_message('inference', 'label_path', language), value=get_cache("list", "path_input"))
				file_input  = gr.Textbox(label=get_message('inference', 'label_filename', language), value=get_cache("list", "file_input"))
				# gr.Audioのラベルは変更できない
				#voice_player= gr.Audio(label=get_message('inference', 'label_voice', language), type="filepath", show_label=True, show_download_button=False, value=get_cache("list", "voice_player"))
				voice_player= gr.Audio(label="Voice", type="filepath", show_label=True, show_download_button=False, value=get_cache("list", "voice_player"))

		with gr.Row():
			with gr.Column():
				output_input = gr.Textbox(label=get_message('inference', 'label_output_path', language), elem_id="Output", value=get_output_value(), interactive=get_output_interactive())
				if len(game_options) > 1:
					game_radio = gr.Radio(label=get_message('inference', 'label_output_destination', language), choices=game_options, value=get_cache("list", "game_radio"))
				else:
					game_radio = gr.Radio(label=get_message('inference', 'label_output_destination', language), choices=game_options, value="0", visible=False)
				output_button = gr.Button(get_message('inference', 'button_output_start', language))

		# メッセージ表示
		with gr.Row():
			message = gr.Textbox(label=get_message('inference', 'label_message', language), interactive=False)

		with gr.Row():
			if kk_path is not None:
				kk_button = gr.Button(get_message('inference', 'button_start_koikatu', language))
			if kks_path is not None:
				kks_button = gr.Button(get_message('inference', 'button_start_koikatsu_sunshine', language))
			if kkp_path is not None:
				kkp_button = gr.Button(get_message('inference', 'button_start_koikatsu_party', language))

		# ----------------------------------------------------------------------
		# イベントハンドラ

		outputs=[
			title_markdown, 
			list_model_dropdown, 
			list_character_dropdown, 
			df_reload_button, 
			df_output, 
			edit_markdown, 
			add_button, 
			update_button, 
			delete_button, 
			model_input, 
			id_input, 
			character_dropdown, 
			category_dropdown, 
			words_input, 
			path_input, 
			file_input, 
			output_input, 
			game_radio, 
			output_button, 
			message 
		]

		if kk_path is not None:
			outputs.append(kk_button)
		if kks_path is not None:
			outputs.append(kks_button)
		if kkp_path is not None:
			outputs.append(kkp_button)

		language_dropdown.change(
			fn=change_language,
			inputs=[
				language_dropdown, 
				list_model_dropdown, 
				list_character_dropdown, 
				character_dropdown, 
				category_dropdown
			], 
			outputs=outputs
		)

		df_reload_button.click(
			fn=get_records,
			outputs=df_output
		)
		first_button.click(
			fn=move_first,
			inputs=id_input,
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		prev_button.click(
			fn=move_prev,
			inputs=id_input,
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		next_button.click(
			fn=move_next,
			inputs=id_input,
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		last_button.click(
			fn=move_last,
			inputs=id_input,
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		add_button.click(
			fn=add_record,
			inputs=[
				character_dropdown, 
				category_dropdown, 
				words_input, 
				path_input, 
				file_input
			],
			outputs=[
				message, 
				df_output, 
				id_input, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		update_button.click(
			fn=update_record,
			inputs=[
				id_input, 
				character_dropdown, 
				category_dropdown, 
				words_input, 
				path_input, 
				file_input
			],
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button 
			]
		)
		delete_button.click(
			fn=delete_record,
			inputs=[id_input],
			outputs=[
				message, 
				df_output, 
				first_button, 
				prev_button, 
				next_button, 
				last_button, 
				model_input, 
				id_input, 
				character_dropdown, 
				category_dropdown, 
				words_input, 
				path_input, 
				file_input
			]
		)
		df_output.select(
			fn=select_record,
			inputs=None,
			outputs=[
				first_button, 
				prev_button, 
				next_button, 
				last_button, 
				model_input, 
				id_input, 
				character_dropdown, 
				category_dropdown, 
				words_input, 
				path_input, 
				file_input
			]
		)

		# キャッシュ保存トリガー
		list_model_dropdown.change(    fn=update_list_model,     inputs=list_model_dropdown)
		list_character_dropdown.change(fn=update_list_character, inputs=list_character_dropdown)
		model_input.change(fn=update_model, inputs=model_input)
		id_input.change(   fn=update_id,    inputs=id_input)
		character_dropdown.change(fn=update_character, inputs=character_dropdown)
		category_dropdown.change( fn=update_category,  inputs=category_dropdown)
		words_input.change(fn=update_words, inputs=words_input)
		path_input.change( fn=update_path_file, inputs=[path_input, file_input], outputs=voice_player)
		file_input.change( fn=update_path_file, inputs=[path_input, file_input], outputs=voice_player)

		output_input.change(fn=update_output, inputs=[output_input, game_radio])
		game_radio.select(fn=select_game, inputs=game_radio, outputs=output_input)

		output_button.click(
			fn=output_contents,
			inputs=[output_input, game_radio], 
			outputs=[message]
		)

		if kk_path is not None:
			kk_button.click(fn=kk_run)
		if kks_path is not None:
			kks_button.click(fn=kks_run)
		if kkp_path is not None:
			kkp_button.click(fn=kkp_run)

	return demo

# ============================================================================ #
#                                [ メイン関数 ]                                #
# ============================================================================ #
if __name__ == "__main__":

	# コンフィグファイルを読み込む
	with open('config.json', 'r', encoding='utf-8') as f:
		data = json.load(f)
	global conf
	conf = parse_json(data)

	demo = create_interface()
	demo.launch(inbrowser=True)
