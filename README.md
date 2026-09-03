# Zotero 图文精读笔记

给 Codex 一篇文章的名字，读取 Zotero 中的全文，生成中文精读笔记，嵌入论文原图，并保存到对应文献下。

**可以选择自己的模板；没有自己的模板时，直接使用随包提供的默认模板。**

这是运行在 Codex 中的 Skill。Zotero 桌面端负责文献和笔记存储。当前已验证 Windows + Zotero 9 个人文库；其他系统和群组文库的自动写回尚未验证。

## 能做什么

- 按标题或可辨识简称查找文章，核对作者、年份、DOI 和 PDF。
- 阅读全文、方法与图注，按所选模板整理研究问题、方法、结果和局限。
- 默认包含全部主图，并按需要补充关键补充图；使用论文原图，添加图号和 PDF 页码跳转。
- 将图片保存为 Zotero 真正的嵌入式附件，保留自定义模板的栏目与编辑器支持的样式。
- 保存修改前快照，检查目标与并发修改，避免重复运行造成重复配图。

## 安装与准备

需要能运行本地技能的 Codex 桌面环境、Zotero Desktop、个人文库中的文章 PDF，以及相应文件访问权限。

推荐在 Codex 中连接 Zotero 插件，并具备 PDF 阅读/图像查看能力。当前 Windows 写回方案需要 Computer Use 控制 Zotero；如果环境提供可用的正式笔记与图片写入工具，可优先使用。安装本技能不会自动安装这些插件。

在 Codex 中发送：

```text
使用 skill-installer 安装这个技能：
https://github.com/15353502638/zotero-paper-notes/tree/main/skills/zotero-paper-notes
```

也可下载仓库，将 `skills/zotero-paper-notes` 整个文件夹复制到自己的 Codex 技能目录（通常是 `~/.codex/skills/`，或当前环境配置的 `$CODEX_HOME/skills/`）。确保 `SKILL.md` 直接位于 `zotero-paper-notes` 文件夹内。下一轮对话查看是否已发现技能；未出现时重新打开 Codex。

附带 Python 工具使用 `pypdf` 与 `Pillow`；环境已有时无需重复安装。手动安装依赖可在仓库目录执行：

```sh
python -m pip install -r skills/zotero-paper-notes/requirements.txt
```

PDF 渲染和视觉检查由当前环境的 PDF/图像工具完成；Python helper 不是全文精读模型，也不会自行操作桌面。

## 使用示例

### 没有自己的模板

```text
使用 $zotero-paper-notes，为《文章完整标题》生成含原图的精读笔记，
使用内置默认模板，并写回 Zotero。
```

默认模板包含基本信息、标题与摘要翻译、前言、方法、结果、讨论/结论/局限、创新、疑问和阅读评价。查看 [默认模板](skills/zotero-paper-notes/assets/note-template.html)。

### 使用自己的模板

可以提供模板文件、粘贴栏目结构、指定 Zotero/Better Notes 中的模板名称，或指定一份空白模板笔记：

```text
使用 $zotero-paper-notes 处理《文章完整标题》，
模板用我上传的 HTML 文件，保留它的栏目和颜色，插入原图后写回 Zotero。
```

```text
给《文章完整标题》做精读笔记，使用 Zotero 里名为“我的文献精读”的模板并写回。
```

选择顺序：**本次指定 → 已约定的个人模板 → 可明确识别的 Zotero 空白实例/当前模板 → 内置默认模板**。明确指定的模板无法读取时会提示补充文件，不会悄悄换成默认模板。多个模板无法区分时，只询问需要选择的模板。

自定义模板无需使用内置字段名称；HTML、Markdown 和纯文本结构均可作为参考。模板中没有图片占位符时，可在相关正文栏目插图。模板明确要求纯文字时遵从该要求。详细规则见 [模板说明](skills/zotero-paper-notes/references/templates.md)。

### 以后只发文章名

先告诉 Codex：

```text
以后在这个文献阅读流程中，我只发文章名时，就运行 $zotero-paper-notes：
生成中文图文精读笔记并写回 Zotero。
优先使用我指定的模板，没有个人模板时使用内置默认模板。
```

之后在保留该约定的对话中发送文章名即可。新对话中如果没有保存这项偏好，请显式调用技能或重新说明。安装技能本身不代表对所有文章的写回授权。

只想看草稿时可以说“只生成草稿，先不写回”；已有人工笔记默认保留。每次生成的是文章自己的笔记实例，不修改 Zotero 的全局模板。

## 写回方式与范围

读取使用 Zotero 的本地只读 API。附带 helper 只准备与核验任务；实际写回通过 Zotero 内置 JavaScript 运行器执行，并使用 Zotero API 管理嵌入式图片。它不直接编辑文库数据库。

写入前检查笔记父条目和旧内容；执行时记录已创建图片与阶段。部分失败时先核查现状，不能删除记录后盲目重跑。缺少全文、模板或写入能力时，会说明缺失内容；仅生成本地副本不会报告为已写回。

详细操作见 [operations.md](skills/zotero-paper-notes/references/operations.md)。论文结论与 AI 辅助评价会区分标注，便于回到原文核查。

## 验证

开发时已在真实 Zotero 笔记验证主图嵌入、来源页码链接和原有内容保留。公开包的自动检查使用合成数据，不访问文献库：

```sh
python -m unittest discover -s tests -p "test_*.py"
node tests/test_writer.mjs
```

Python 检查需要上述依赖；JavaScript 模拟检查需要 Node.js 18 或以上。自动检查覆盖任务准备、占位符与目标检查、图片校验、成功重试不重复添加，以及部分失败后的停止行为；它们不替代不同 Zotero 版本中的实际排版验证。

## 发布内容与许可

仓库包含技能说明、工具脚本、空白默认模板和合成测试，不包含个人文库、文章 PDF、原文图片或真实精读笔记。默认模板由最初使用者提供并允许随项目分享，使用者也可复制并修改自己的模板。

项目代码、说明和随附空白模板按 [MIT License](LICENSE) 发布。处理的论文及其图片仍适用各自的使用条件，不随本项目获得许可。
