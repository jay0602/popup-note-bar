# 彈出記事欄（Popup Note Bar）

一個輕量、鍵盤優先的 Windows 浮動記事工具。按下 `Ctrl + Alt + N`，即可在任何工作流程中叫出或隱藏記事欄。

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

## 功能

- 全域快捷鍵 `Ctrl + Alt + N`
- 多則記事與即時搜尋
- 輸入後自動儲存
- 視窗置頂與失焦自動收起
- 系統匣常駐
- 純本機資料，不需要帳號或網路
- 原子寫入，降低儲存中斷造成的資料損壞風險

## 下載

一般使用者請到 [Releases](../../releases) 下載 Windows ZIP，解壓縮後執行：

```text
彈出記事欄程式\彈出記事欄.exe
```

請保留 `_internal` 資料夾與 EXE 在一起。

## 從原始碼執行

需要 Windows 10/11 與 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python popup_note_bar.py
```

## 資料位置

記事內容儲存在：

```text
%LOCALAPPDATA%\PopupNoteBar\notes.json
```

程式不會把記事上傳到網路。建議重要內容仍定期備份。

## 快捷鍵被占用

若其他程式已使用 `Ctrl + Alt + N`，程式會在底部顯示提醒。此時仍可透過 Windows 系統匣圖示開啟記事欄。

## 測試

```powershell
.\.venv\Scripts\python -m unittest -q test_note_store.py
```

## 建立 Windows 發行版

```powershell
.\.venv\Scripts\python -m pip install pyinstaller
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --windowed --name "彈出記事欄" popup_note_bar.py
```

## 授權

[MIT License](LICENSE)
