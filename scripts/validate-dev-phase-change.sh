#!/usr/bin/env bash
# validate-dev-phase-change.sh
# 校验给定 Dev-Phase 变更目录的 proposal.md 与 design.md 是否包含本变更 design.md 附录 A 定义的所有必填章节。
#
# 用法:
#   bash scripts/validate-dev-phase-change.sh <change-dir>
#
# 退出码:
#   0 = 全部必填章节齐全
#   1 = 存在缺失章节（已打印缺失清单到 stderr）
#
# 依据: openspec/changes/setup-development-roadmap/design.md 附录 A

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <change-dir>" >&2
    echo "Example: $0 openspec/changes/dev-phase-0-engine-core" >&2
    exit 2
fi

CHANGE_DIR="$1"

if [[ ! -d "$CHANGE_DIR" ]]; then
    echo "ERROR: change directory does not exist: $CHANGE_DIR" >&2
    exit 2
fi

PROPOSAL="$CHANGE_DIR/proposal.md"
DESIGN="$CHANGE_DIR/design.md"

if [[ ! -f "$PROPOSAL" ]]; then
    echo "ERROR: proposal.md not found in $CHANGE_DIR" >&2
    exit 2
fi

if [[ ! -f "$DESIGN" ]]; then
    echo "ERROR: design.md not found in $CHANGE_DIR" >&2
    exit 2
fi

# 必填章节锚点（来自 design.md 附录 A）
# 格式: "文件:锚点正则:人类可读描述"
PROPOSAL_ANCHORS=(
    "^## Why$:proposal:Why 章节"
    "^## What Changes$:proposal:What Changes 章节"
    "^## Capabilities$:proposal:Capabilities 章节"
    "^## Impact$:proposal:Impact 章节"
    "^### 跨阶段接口变更登记$:proposal:跨阶段接口变更登记 子章节"
    "^## Regression Baseline$:proposal:Regression Baseline 章节"
)

DESIGN_ANCHORS=(
    "^## Context$:design:Context 章节"
    "^## Goals / Non-Goals$:design:Goals / Non-Goals 章节"
    "^## Decisions$:design:Decisions 章节"
    "^## Risks / Trade-offs$:design:Risks / Trade-offs 章节"
    "^## DoD Checklist$:design:DoD Checklist 章节"
    "^## No-Go Rollback Plan$:design:No-Go Rollback Plan 章节"
)

missing=0
missing_list=""

check_anchor() {
    local file="$1"
    local pattern="$2"
    local label="$3"

    # 使用 grep -E（POSIX ERE）；锚点形如 "^## XYZ$" 精确匹配标题行
    # 允许末尾有可选空白
    if ! grep -qE "${pattern}" "$file"; then
        echo "MISSING: [$label] in $(basename "$file") (pattern: $pattern)" >&2
        missing=$((missing + 1))
        missing_list="${missing_list}- [$label] in $(basename "$file")\n"
    fi
}

echo "Validating Dev-Phase change at: $CHANGE_DIR"
echo "Checking proposal.md anchors..."
for anchor in "${PROPOSAL_ANCHORS[@]}"; do
    IFS=':' read -r pattern file_label human_label <<< "$anchor"
    check_anchor "$PROPOSAL" "$pattern" "$human_label"
done

echo "Checking design.md anchors..."
for anchor in "${DESIGN_ANCHORS[@]}"; do
    IFS=':' read -r pattern file_label human_label <<< "$anchor"
    check_anchor "$DESIGN" "$pattern" "$human_label"
done

echo "------------------------------------------"
if [[ $missing -eq 0 ]]; then
    echo "PASS: All required sections present."
    exit 0
else
    echo "FAIL: $missing required section(s) missing." >&2
    echo "" >&2
    echo "Missing sections:" >&2
    printf "%b" "$missing_list" >&2
    echo "" >&2
    echo "Refer to openspec/changes/setup-development-roadmap/design.md Appendix A for the template." >&2
    exit 1
fi
