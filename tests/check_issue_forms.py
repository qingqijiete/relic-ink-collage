#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 .github/ISSUE_TEMPLATE 下的 issue forms 结构。

GitHub 对模板的校验是静默的：字段写错（id 重复、缺 attributes.label、
type 拼错）不会报错，只会让整个 Issue 选择页退回空白模板。这个脚本让
问题在 CI 里显式暴露。

用法：python tests/check_issue_forms.py
依赖：pyyaml（CI 中安装；本地未安装时跳过而不是报失败）
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:                                    # pragma: no cover
    print("skip: pyyaml 未安装，跳过模板校验（CI 中会执行）")
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / ".github" / "ISSUE_TEMPLATE"

TOP_KEYS = {
    "name", "description", "title", "labels", "assignees", "projects",
    "type", "body",
}
FIELD_TYPES = {
    "markdown", "textarea", "input", "dropdown", "checkboxes", "upload",
}
# 与 CONTRIBUTING.md 的「四类贡献」一一对应
REQUIRED_LABELS = {"failure-mode", "choreography", "scripts", "prompt-template"}


def validate_form(path, text, errors):
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        errors.append(f"{path.name}: 顶层不是映射")
        return set()
    for key in data:
        if key not in TOP_KEYS:
            errors.append(f"{path.name}: 顶层字段 {key!r} 不受支持")
    for key in ("name", "description", "body"):
        if not data.get(key):
            errors.append(f"{path.name}: 缺少必填字段 {key}")

    labels = data.get("labels") or []
    labels = [labels] if isinstance(labels, str) else labels

    body = data.get("body")
    if not isinstance(body, list) or not body:
        errors.append(f"{path.name}: body 必须是非空列表")
        return set(labels)

    seen_ids = []
    for index, item in enumerate(body, 1):
        where = f"{path.name}: body[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} 不是映射")
            continue
        field = item.get("type")
        if field not in FIELD_TYPES:
            errors.append(f"{where} type={field!r} 非法")
            continue
        attrs = item.get("attributes")
        if not isinstance(attrs, dict):
            errors.append(f"{where} 缺少 attributes")
            continue
        if field == "markdown":
            if not attrs.get("value"):
                errors.append(f"{where} markdown 缺少 value")
            if "id" in item:
                errors.append(f"{where} markdown 不应带 id")
            continue

        field_id = item.get("id")
        if not field_id:
            errors.append(f"{where} 缺少 id")
        else:
            seen_ids.append(str(field_id))
        if not attrs.get("label"):
            errors.append(f"{where} 缺少 attributes.label")
        if field in ("dropdown", "checkboxes"):
            options = attrs.get("options")
            if not isinstance(options, list) or not options:
                errors.append(f"{where} 缺少 attributes.options")
                continue
            for option in options:
                if isinstance(option, dict) and not option.get("label"):
                    errors.append(f"{where} options 子项缺少 label")
        validations = item.get("validations")
        if validations is not None and not isinstance(validations, dict):
            errors.append(f"{where} validations 不是映射")
        elif isinstance(validations, dict) and not isinstance(
            validations.get("required", True), bool
        ):
            errors.append(f"{where} validations.required 必须是布尔值")

    duplicated = {i for i in seen_ids if seen_ids.count(i) > 1}
    if duplicated:
        errors.append(f"{path.name}: id 重复 {sorted(duplicated)}")
    return set(labels)


def main():
    if not TPL.is_dir():
        print(f"skip: 没有 {TPL}")
        return 0
    errors = []
    used_labels = set()

    for path in sorted(TPL.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if path.name == "config.yml":
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                errors.append("config.yml: 顶层不是映射")
                continue
            if not isinstance(data.get("blank_issues_enabled"), bool):
                errors.append("config.yml: blank_issues_enabled 必须是布尔值")
            for index, link in enumerate(data.get("contact_links") or [], 1):
                if not isinstance(link, dict):
                    errors.append(f"config.yml: contact_links[{index}] 不是映射")
                    continue
                for key in ("name", "url", "about"):
                    if not link.get(key):
                        errors.append(f"config.yml: contact_links[{index}] 缺少 {key}")
                if not str(link.get("url", "")).startswith("http"):
                    errors.append(f"config.yml: contact_links[{index}] url 不是 http(s)")
            continue
        used_labels |= validate_form(path, text, errors)

    missing = REQUIRED_LABELS - used_labels
    if missing:
        errors.append(f"以下标签没有任何模板使用：{sorted(missing)}")

    for message in errors:
        print(f"ERROR {message}")
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
