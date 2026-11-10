#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YAML audit for legal decision-tree Markdown samples.

Usage:
  python yaml_audit.py sample.md
  python yaml_audit.py sample.md --law-text law.docx
  python yaml_audit.py sample.md --law-text law.txt --strict --json report.json
"""
import argparse, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
from collections import Counter
try:
    import yaml
except Exception as e:
    print('ERROR: PyYAML not installed:', e)
    sys.exit(2)

ALLOWED_RULE_TYPES = {'definition','condition','obligation','exception','procedure','penalty'}
ALLOWED_ACTION_TYPES = {'obligation','permission','prohibition'}
ALLOWED_OPS = {'equals','in','gte','lte','exists','not_exists','not_equals'}
REQUIRED = ['rule_id','title','law','article','rule_type','description','condition','action','legal_basis','verification']
PLACEHOLDERS = ['XXXXXXXX','???','[待填]','TODO','待补充']

CN_NUM = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cn2int(s):
    if s.isdigit():
        return int(s)
    total = 0; section = 0; num = 0
    for ch in s:
        if ch in CN_NUM:
            num = CN_NUM[ch]
        elif ch == '十':
            section += (num if num else 1) * 10; num = 0
        elif ch == '百':
            section += (num if num else 1) * 100; num = 0
        elif ch == '千':
            section += (num if num else 1) * 1000; num = 0
        else:
            raise ValueError('bad cn number: ' + s)
    return total + section + num

def extract_articles(text):
    out = set()
    for m in re.finditer(r'第([零一二三四五六七八九十百千0-9]+)条', text):
        try: out.add(cn2int(m.group(1)))
        except Exception: pass
    return out

def norm(s):
    s = s or ''
    s = s.replace('\u3000',' ')
    s = re.sub(r'\s+', '', s)
    return s

def read_law_text(path):
    if not path:
        return ''
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        from docx import Document
        doc = Document(path)
        return '\n'.join(p.text for p in doc.paragraphs)
    return open(path, encoding='utf-8', errors='ignore').read()

def blocks(text):
    pat = re.compile(r'```ya?ml\s*\n(.*?)```', re.S | re.I)
    for m in pat.finditer(text):
        line = text[:m.start()].count('\n') + 1
        yield line, m.group(1)

def add(issues, sev, block_line, msg, rule_id=''):
    issues.append({'severity':sev, 'line':block_line, 'rule_id':rule_id, 'message':msg})

def check_doc(d, block_line, issues, official, official_articles):
    rid = str(d.get('rule_id') or '')
    if not isinstance(d, dict):
        add(issues,'ERROR',block_line,'YAML 顶层不是 mapping'); return
    for k in REQUIRED:
        if k not in d or d[k] in (None,'',[],{}):
            add(issues,'ERROR',block_line,f'缺少或为空字段: {k}',rid)
    rt = d.get('rule_type')
    if rt and rt not in ALLOWED_RULE_TYPES:
        add(issues,'ERROR',block_line,f'非法 rule_type: {rt}',rid)
    art = str(d.get('article') or '')
    if '第N条' in art or not re.search(r'第[零一二三四五六七八九十百千0-9]+条', art):
        add(issues,'ERROR',block_line,f'article 占位符或格式异常: {art}',rid)
    else:
        m = re.search(r'第([零一二三四五六七八九十百千0-9]+)条', art)
        if m and official_articles:
            try:
                n = cn2int(m.group(1))
                if n not in official_articles:
                    add(issues,'ERROR',block_line,f'article 不存在于官方原文: 第{n}条',rid)
            except Exception:
                pass
    act = d.get('action')
    if act:
        if not isinstance(act, list):
            add(issues,'ERROR',block_line,'action 必须是 list',rid)
        else:
            for a in act:
                if not isinstance(a, dict) or a.get('type') not in ALLOWED_ACTION_TYPES:
                    add(issues,'ERROR',block_line,f'action.type 非法: {a}',rid)
    cond = d.get('condition')
    if cond is not None:
        if not isinstance(cond, dict):
            add(issues,'ERROR',block_line,'condition 必须是 mapping',rid)
        else:
            for key in ('all','any','none'):
                if key in cond and not isinstance(cond[key], list):
                    add(issues,'ERROR',block_line,f'condition.{key} 必须是 list',rid)
            for grp in ('all','any','none'):
                for c in cond.get(grp,[]) or []:
                    if isinstance(c, dict) and c.get('operator') not in ALLOWED_OPS:
                        add(issues,'ERROR',block_line,f'非法 operator: {c.get("operator")}',rid)
    lb = d.get('legal_basis')
    quote = ''
    if isinstance(lb, dict):
        quote = str(lb.get('quote') or '')
    if not quote:
        add(issues,'ERROR',block_line,'legal_basis.quote 为空',rid)
    elif official:
        if norm(quote) not in norm(official):
            add(issues,'WARN',block_line,'quote 未在官方文本中逐字匹配（可能标点/改字/拼接）',rid)
    if 'verification' not in d or not isinstance(d.get('verification'),dict):
        add(issues,'ERROR',block_line,'verification 缺失或不是 mapping',rid)
    elif d['verification'].get('status') not in ('pending','verified'):
        add(issues,'WARN',block_line,'verification.status 建议为 pending 或 verified',rid)
    for k,v in d.items():
        s = str(v)
        for ph in PLACEHOLDERS:
            if ph in s:
                add(issues,'ERROR',block_line,f'占位符残留: {ph}',rid)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sample')
    ap.add_argument('--law-text', default='')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    text = open(a.sample, encoding='utf-8', errors='ignore').read()
    official = read_law_text(a.law_text)
    official_articles = extract_articles(official) if official else set()
    issues=[]; docs=[]; seen=Counter(); block_count=0
    for line, block in blocks(text):
        block_count += 1
        try:
            parsed = list(yaml.safe_load_all(block))
        except Exception as e:
            add(issues,'ERROR',line,'YAML 解析失败: '+str(e).replace('\n',' '))
            continue
        for d in parsed:
            if d is None: continue
            docs.append(d)
            rid = str(d.get('rule_id') or '') if isinstance(d,dict) else ''
            if rid: seen[rid]+=1
            check_doc(d,line,issues,official,official_articles)
    for rid,n in seen.items():
        if n>1: add(issues,'ERROR',0,f'rule_id 重复 {n} 次: {rid}',rid)
    errs=[x for x in issues if x['severity']=='ERROR']
    warns=[x for x in issues if x['severity']=='WARN']
    print('='*70)
    print('file:', a.sample)
    print('yaml_blocks:', block_count, 'parsed_docs:', len(docs), 'unique_rule_ids:', len(seen))
    print('official_articles:', len(official_articles), 'errors:', len(errs), 'warnings:', len(warns))
    for x in issues:
        print(f"[{x['severity']}] line {x['line']} {x['rule_id']} {x['message']}")
    print('='*70)
    if a.json:
        json.dump({'sample':a.sample,'blocks':block_count,'docs':len(docs),'issues':issues}, open(a.json,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    bad = bool(errs) or (a.strict and bool(warns))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())

