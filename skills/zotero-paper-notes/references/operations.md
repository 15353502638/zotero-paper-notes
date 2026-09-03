# 本地 Zotero 图文写回

## 连接与读取

先按 Zotero 技能执行 `status --json`。若 status 因配置目录访问失败，而本地 API 已可连接，可继续使用正常只读 API；这不是申请额外文件权限的替代方式。确需受限文件时按环境请求具体路径权限。

helper 常用命令：`search "标题" --json`、`children KEY --json`、`fulltext ATTACHMENT_KEY --out FILE`、`file-url ATTACHMENT_KEY`。

个人文库 API：`http://127.0.0.1:23119/api/users/0/items/KEY`，HTML 在 `data.note`。本地 REST API 只读，不向它发 PATCH/PUT，不直接改 zotero.sqlite。

Python 不在 PATH 时使用当前 `load_workspace_dependencies` 返回的 Python，Windows 添加 `-X utf8`。PowerShell 不用 `\"` 转义内层引号，复杂代码放脚本文件；正确引用带中文、空格的路径。

## 通用准备脚本

`scripts/note_job.py` 只读取 Zotero、写任务工作区，不修改文献库。`prepare` 创建供 Zotero 内置运行器执行的脚本。先在 Zotero 确定或创建目标子笔记；helper 不根据模糊标题自动选写入位置。内置 helper 仅支持个人文库；群组库须另行核对正确接口与 libraryID。

```text
python -X utf8 <skill>/scripts/note_job.py snapshot --parent PARENT_KEY --note NOTE_KEY --out work/note-before.json
python -X utf8 <skill>/scripts/note_job.py extract --pdf FILE.pdf --page 45 --index 0 --out work/figure-1.jpg
python -X utf8 <skill>/scripts/note_job.py prepare --snapshot work/note-before.json --html work/final-note.html --images work/images.json --out work/note-job.json
python -X utf8 <skill>/scripts/note_job.py verify --job work/note-job.json
```

key/page 必须来自当前文章。`extract` 只提取指定页的一个图像对象，不能判断其是否为完整主图。需要渲染时按 PDF 技能操作或用已有 pypdfium2，不能假设 PyMuPDF 总在环境中。

`final-note.html` 含完整正文，在插图位置放唯一标记，如 `{{FIG1}}`。`images.json` 格式：

```json
[{"marker":"{{FIG1}}","file":"figure-1.jpg","caption":"Fig.1｜研究设计与筛选结果","pdfKey":"ACTUALPDFKEY","page":1,"width":900}]
```

`file` 相对 images.json 目录或为绝对路径。`pdfKey` 必须是该文献真实 PDF 附件 key；`page` 从 1 起算。图片尺寸用 Pillow 检查，显示高度等比例。支持 PNG/JPEG。`prepare` 生成任务 JSON 及同名 `.run.js`；运行后生成 `.result.json` 阶段记录。

任务首次运行会在修改前记录阶段；成功后记录最终 HTML 和图片 key。再次运行已完成任务仅返回结果，不重复添加。若记录显示正在写入或部分失败，拒绝继续；先只读核查实际库，不能删除阶段记录强行重试。

## Windows 内置运行器

遵循 Computer Use 的 `node_repl` + `@oai/sky` 两步观察/操作流程。若截到 Codex/其他应用而不是 Zotero，不用该画面的坐标点击；先激活真实目标并重看。

打开“工具 → 开发者 → Run JavaScript”，通过 `list_windows` 获取新窗口，不构造 handle。点击代码区、验证焦点，把 `.run.js` 全文输入。含 `await` 时确认“作为异步函数执行”已选中，再执行。回显可能短暂仍是上次结果，重新观察再判断，不因旧报错立即重跑。

核心接口：

```js
var n = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, noteKey);
// 检查 isNote、parentItemKey、getNote 与快照一致
var a = await Zotero.Attachments.importEmbeddedImage({
  blob: new Blob([bytes], {type:"image/jpeg"}), parentItemID:n.id
});
// HTML: <img data-attachment-key="REALKEY" width="900" height="614">
n.setNote(html);
await n.saveTx();
```

Windows IOUtils 要求反斜杠路径，附带脚本已转换。让 Zotero 管理附件，不手工创建 storage 目录、伪造 key 或用磁盘 src 冒充嵌入。

## 核验与恢复

`verify` 再读笔记和嵌入附件，检查正文语义、标题/颜色等结构、图像数量顺序、父子关系与图像散列。Zotero 会加 `rel` 并规范化空白，不能仅以 HTML 字节不相等判失败。原用户内容保留还需助手审阅。

能操作时查看最终排版。导出本地 HTML 时把 key 引用转换成可移植图片，不仅导出无效 key。部分失败先核查记录与实际库，已导入图片应恢复其引用，不重复导入。旧内容检查失败时重新读、比较、合并。

核对版本时参考 [Zotero JS API](https://www.zotero.org/support/dev/client_coding/javascript_api)、[attachments.js](https://github.com/zotero/zotero/blob/main/chrome/content/zotero/xpcom/attachments.js) 的 `importEmbeddedImage`、[笔记说明](https://www.zotero.org/support/notes)。
