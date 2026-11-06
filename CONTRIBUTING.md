# 参与贡献

欢迎提 issue 和 PR。这个技能的价值在于**可复现的构图规则**，所以改动时优先补充可验证的经验，而不是堆形容词。

## 值得贡献的几类改动

四类贡献各有对应的 issue 模板，点「New issue」会直接看到：

| 类型 | 适合提交什么 | 模板 |
| --- | --- | --- |
| **失败模式** | 你生成的图出现了没被现有文档覆盖的问题（器物多出一件、纸带中断、伪铭文、切片变成规则网格……），带上现象、成因与修正后的提示词句式 | [画面失败模式](https://github.com/qingqijiete/relic-ink-collage/issues/new?template=1-failure-mode.yml) |
| **动线结构** | 新的贯穿结构（例如「双纸带交叉」「环形回绕」），需要给出九格边界参数，并附至少一张实测成品 | [新动线提案](https://github.com/qingqijiete/relic-ink-collage/issues/new?template=2-choreography.yml) |
| **脚本** | 修 bug 或增加通用能力（例如素材板支持 10 张以上、拼合支持 2×2 / 4×4 版式） | [脚本问题或需求](https://github.com/qingqijiete/relic-ink-collage/issues/new?template=3-scripts.yml) |
| **提示词模板** | 针对特定器物类型（长条玉器、镂空器、造像）的约束句 | [提示词模板改进](https://github.com/qingqijiete/relic-ink-collage/issues/new?template=4-prompt-template.yml) |

## 提交前

```bash
python -m pip install -r requirements.txt
python -m py_compile scripts/*.py
python tests/smoke_test.py
```

改了 issue 模板就再跑一遍 `python tests/check_issue_forms.py`（需 `pip install pyyaml`）。GitHub 对模板的字段错误是静默失败的——写错 id 或漏掉 label，新建 Issue 会直接退回空白模板，所以这一项交给 CI 挡。

如果改动涉及画面规则，请在 PR 描述里贴一张前后对照图。

## 不要做的事

- 不要提交你没有授权的图片。示例图必须是自己拍摄或明确可商用，且不含展签、观众面部。
- 不要在提示词模板里加入「推断年代 / 补全铭文 / 复原残缺部分」这类要求，这与技能护栏冲突。
- 不要把 `references/` 里的规则改写成含糊的风格形容词；规则要能被检查。

## 许可

提交即表示同意以 [MIT](LICENSE) 许可发布你的贡献。
