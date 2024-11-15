# 文字转语音应用程序
# edge-tts-ui

这个应用程序是一个使用 `edge-tts` 库和 PyQt5 创建的文本转语音（TTS）工具。它允许用户输入文本，从多种声音中选择，通过插入静音片段来实现插入停顿，并生成 MP3 格式的语音输出。

## 界面预览
![00](https://github.com/smallnew666/edge-tts-ui/assets/24582880/67474188-29bc-48af-91c6-8ad5ad823ea8)

## 特性
- 输入文本以生成语音。
- 选择不同的声音进行语音合成。
- 控制语音的速度和音量。
- 在语音中插入停顿的能力。
- 回放功能以预览生成的语音。
- 将语音输出导出为 MP3 文件。
## 系统要求
- Python 3
- PyQt5
- edge-tts
- lameenc
## 安装

要使用该应用程序，请克隆此仓库并安装所需的依赖项：

```bash
git clone https://github.com/smallnew666/edge-tts-ui.git
cd edge-tts-ui
pip install -r requirements.txt
```


## 使用方法

通过执行主 Python 脚本来运行应用程序：

```bash
python app.py
```
