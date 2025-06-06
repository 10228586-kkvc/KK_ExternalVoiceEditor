# KK_ExternalVoiceEditor

** 概要 **
- コイカツのキャラスタジオで、任意ボイスを使用するKK_ExternalVoiceLoaderのデータ編集補助ツール（KK_ExternalVoiceLoaderは用意しなくてよい）

** インストール **
1. 任意のフォルダにダウンロードしたInstall-ExternalVoiceEditor.batを設置してダブルクリックする。
2. Environment setup is complete.と表示されたらウィンドウを閉じる。
3. 作成されたKK_ExternalVoiceEditorフォルダ内にあるApp.batをダブルクリックする。

![KK_ExternalVoiceEditor](https://github.com/user-attachments/assets/b2db9be1-f55f-4a8b-a56a-d7e9f28de684)

** 使い方 **
- モデル: 現在未使用（AI音声合成で生成したモデルの情報を選択の予定）
- 性格: コイカツの性格
- リロード: 選択したモデル、性格でボイス一覧へ反映
- ボイス一覧: クリックして選択
- △▲▼▽: 選択したボイスの並び順を変更、最上部・上部・下部・最下部へ移動
- 追加: ボイス情報を追加
- 変更: ボイス情報を変更
- 削除: ボイス情報を削除
- 音声: 選択したボイスを再生
- 出力パス: ボイス（wavファイル）、プラグイン（KK_ExternalVoiceLoader.dll、KKS_ExternalVoiceLoader.dll）、ボイスリストmod（KK_KKS_custom-voice-list-1.0.0.zipmod）を指定したパスにインストール
- 出力先: パス指定・コイカツ！・コイカツ！サンシャインの出力先選択（コイカツ！、コイカツ！サンシャインがインストールされていれば表示）
- メッセージ: 実行結果を表示
- 起動ボタン: コイカツ！・コイカツ！サンシャインを起動（コイカツ！、コイカツ！サンシャインがインストールされていれば表示）

** 注意事項 **
- 使用するボイスはUserDataフォルダの中に保存してください。（パスはUserDataフォルダ以降のフォルダ）
- ボイスはwavファイルを使用してください。
- 出力パスがパス指定の場合は、プラグイン（KK_ExternalVoiceLoader.dll、KKS_ExternalVoiceLoader.dll）はコピーされません。
- バックアップを保存したい場合は、app.dbファイルとUserDataフォルダをコピーしてください。この二つを上書きすれば復元できます。
- 音声はパスとファイル名が正しくないと再生できません。
- 出力先選択と起動ボタンはコイカツ！、コイカツ！サンシャインがインストールされていれば表示されます。

** キャラスタジオ（コイカツ！・コイカツ！サンシャイン） **

![コイカツ！のキャラスタジオのボイスに任意の音声データを追加する。](https://github.com/user-attachments/assets/ad7565d3-6bad-4d4d-b05b-489bc206bffb)

** キャラスタジオ音声MODチュートリアル **
[![【コイカツのキャラスタジオ】でキャラが喋る！Timeline＋音声MODの神機能！AIで声優ボイスを再現！ボイス付きのシーンが作れる！【チュートリアル】](https://github.com/user-attachments/assets/9f6396b1-35fa-4822-90d7-27bb9bb046ba)](https://www.youtube.com/watch?v=Aw6TAnGvwCw)

** 関連情報 **
- 外部音声ファイル読み込み KK_ExternalVoiceLoader[[Download>https://github.com/10228586-kkvc/KK_ExternalVoiceLoader]]

- TimelineVoiceControl(Rikki-Koi-Plugins)[[Download>https://github.com/RikkiBalboa/Rikki-Koi-Plugins]]

- Timelineで音声を使う[[チュートリアル>https://www.youtube.com/watch?v=Aw6TAnGvwCw]]

- コイカツ本編セリフ一覧[[kk-studio-add-list>https://github.com/10228586-kkvc/kk-studio-add-list]]

- 音声MODについて[[コイカツ！MODスレ避難所（音声MOD等）>https://jbbs.shitaraba.net/game/61301/]]
