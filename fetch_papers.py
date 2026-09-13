#!/usr/bin/env python3
"""
Ontology 文献追踪自动化脚本
从 arXiv 和 PubMed 获取昨天的 ontology 相关论文
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import os
import yaml
import time
from pathlib import Path
from deep_translator import GoogleTranslator, MyMemoryTranslator


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def translate_to_chinese(text, max_retries=2):
    """将英文文本翻译为中文，失败时返回原文"""
    if not text or not text.strip():
        return ""
    
    text_to_translate = text[:2000]
    
    # 尝试 Google Translate
    for attempt in range(max_retries):
        try:
            result = GoogleTranslator(source='en', target='zh-CN').translate(text_to_translate)
            time.sleep(2)
            return result if result else text
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"  Google 翻译重试 ({attempt+1}/{max_retries})，等待 {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Google 翻译不可用，切换到 MyMemory...")
    
    # 备选: MyMemory Translator（限制 500 字符）
    try:
        short_text = text_to_translate[:450]
        result = MyMemoryTranslator(source='en-GB', target='zh-CN').translate(short_text)
        time.sleep(1)
        return result if result else text
    except Exception as e:
        print(f"  MyMemory 翻译也失败: {e}")
        return text


def translate_papers(papers):
    """为每篇论文生成中文简介（翻译标题和摘要）"""
    total = len(papers)
    
    for i, paper in enumerate(papers, 1):
        print(f"  翻译中 [{i}/{total}]: {paper['title'][:50]}...")
        
        # 翻译标题
        paper['title_zh'] = translate_to_chinese(paper['title'])
        
        # 翻译摘要（截取前 800 字符用于翻译）
        if paper.get('summary'):
            paper['summary_zh'] = translate_to_chinese(paper['summary'][:800])
        else:
            paper['summary_zh'] = ""
    
    return papers


def fetch_arxiv_papers(keywords, max_results=50):
    """
    从 arXiv 获取论文
    使用 arXiv API: http://export.arxiv.org/api/query
    """
    # 构建搜索查询
    query = " OR ".join([f'all:"{kw}"' for kw in keywords])
    
    # arXiv API 参数
    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    try:
        response = requests.get('http://export.arxiv.org/api/query', params=params, timeout=30)
        response.raise_for_status()
        
        # 解析 XML 响应
        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        
        papers = []
        target_date = (datetime.now() - timedelta(days=1)).date()
        
        for entry in root.findall('atom:entry', namespace):
            # 获取发布日期
            published = entry.find('atom:published', namespace).text
            pub_date = datetime.fromisoformat(published.replace('Z', '+00:00')).date()
            
            # 只保留昨天的论文
            if pub_date == target_date:
                paper = {
                    'title': entry.find('atom:title', namespace).text.strip().replace('\n', ' '),
                    'summary': entry.find('atom:summary', namespace).text.strip().replace('\n', ' '),
                    'authors': [author.find('atom:name', namespace).text for author in entry.findall('atom:author', namespace)],
                    'published': published,
                    'url': entry.find('atom:id', namespace).text,
                    'source': 'arXiv'
                }
                
                # 获取 PDF 链接
                for link in entry.findall('atom:link', namespace):
                    if link.get('title') == 'pdf':
                        paper['pdf_url'] = link.get('href')
                        break
                
                papers.append(paper)
        
        return papers
    
    except Exception as e:
        print(f"arXiv 获取失败: {e}")
        return []


def fetch_pubmed_papers(keywords, max_results=50):
    """
    从 PubMed 获取论文
    使用 NCBI E-utilities API
    """
    # 构建搜索查询
    query = " OR ".join(keywords)
    
    # 获取昨天的日期范围
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
    
    try:
        # 第一步：搜索获取 PMID 列表
        search_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        search_params = {
            'db': 'pubmed',
            'term': f"({query}) AND {yesterday}[dp]",
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'date'
        }
        
        search_response = requests.get(search_url, params=search_params, timeout=30)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        id_list = search_data.get('esearchresult', {}).get('idlist', [])
        
        if not id_list:
            return []
        
        # 第二步：获取论文详情
        fetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        fetch_params = {
            'db': 'pubmed',
            'id': ','.join(id_list),
            'retmode': 'xml'
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=30)
        fetch_response.raise_for_status()
        
        # 解析 XML
        root = ET.fromstring(fetch_response.content)
        papers = []
        
        for article in root.findall('.//PubmedArticle'):
            medline = article.find('.//MedlineCitation')
            if medline is None:
                continue
            
            article_elem = medline.find('.//Article')
            if article_elem is None:
                continue
            
            # 标题
            title_elem = article_elem.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ''
            
            # 摘要
            abstract_elem = article_elem.find('.//AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else ''
            
            # 作者
            authors = []
            for author in article_elem.findall('.//Author'):
                lastname = author.find('.//LastName')
                forename = author.find('.//ForeName')
                if lastname is not None:
                    name = lastname.text
                    if forename is not None:
                        name = f"{name} {forename.text}"
                    authors.append(name)
            
            # PMID
            pmid = medline.find('.//PMID').text
            
            # 发布日期
            pub_date_elem = article_elem.find('.//PubDate')
            pub_date = ''
            if pub_date_elem is not None:
                year = pub_date_elem.findtext('Year', '')
                month = pub_date_elem.findtext('Month', '')
                day = pub_date_elem.findtext('Day', '')
                pub_date = f"{year} {month} {day}"
            
            paper = {
                'title': title.strip(),
                'summary': abstract.strip(),
                'authors': authors,
                'published': pub_date,
                'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
                'pmid': pmid,
                'source': 'PubMed'
            }
            
            papers.append(paper)
        
        return papers
    
    except Exception as e:
        print(f"PubMed 获取失败: {e}")
        return []


def save_results(papers, output_dir):
    """保存结果到 JSON 和 Markdown 文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 保存 JSON
    json_path = output_path / f"papers_{yesterday}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    
    # 保存纯文本报告
    txt_path = output_path / f"papers_{yesterday}.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"Ontology 文献追踪报告 - {yesterday}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"共发现 {len(papers)} 篇新论文\n\n")
        
        if papers:
            # 按来源分组
            arxiv_papers = [p for p in papers if p['source'] == 'arXiv']
            pubmed_papers = [p for p in papers if p['source'] == 'PubMed']
            
            if arxiv_papers:
                f.write(f"--- arXiv ({len(arxiv_papers)} 篇) {'-' * 30}\n\n")
                for i, paper in enumerate(arxiv_papers, 1):
                    f.write(f"{i}. {paper['title']}\n")
                    if paper.get('title_zh'):
                        f.write(f"   中文标题: {paper['title_zh']}\n")
                    authors_str = ', '.join(paper['authors'][:5])
                    if len(paper['authors']) > 5:
                        authors_str += f" 等 {len(paper['authors'])} 人"
                    f.write(f"   作者: {authors_str}\n")
                    f.write(f"   链接: {paper['url']}\n")
                    if 'pdf_url' in paper:
                        f.write(f"   PDF: {paper['pdf_url']}\n")
                    if paper.get('summary_zh'):
                        f.write(f"   简介: {paper['summary_zh']}\n")
                    else:
                        f.write(f"   摘要: {paper['summary'][:500]}...\n")
                    f.write("\n")
            
            if pubmed_papers:
                f.write(f"--- PubMed ({len(pubmed_papers)} 篇) {'-' * 30}\n\n")
                for i, paper in enumerate(pubmed_papers, 1):
                    f.write(f"{i}. {paper['title']}\n")
                    if paper.get('title_zh'):
                        f.write(f"   中文标题: {paper['title_zh']}\n")
                    authors_str = ', '.join(paper['authors'][:5])
                    if len(paper['authors']) > 5:
                        authors_str += f" 等 {len(paper['authors'])} 人"
                    f.write(f"   作者: {authors_str}\n")
                    f.write(f"   链接: {paper['url']}\n")
                    f.write(f"   PMID: {paper['pmid']}\n")
                    if paper.get('summary_zh'):
                        f.write(f"   简介: {paper['summary_zh']}\n")
                    elif paper.get('summary'):
                        f.write(f"   摘要: {paper['summary'][:500]}...\n")
                    f.write("\n")
        else:
            f.write("昨天暂无新论文\n")
    
    return json_path, txt_path


def main():
    print(f"开始获取 ontology 相关文献 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载配置
    config = load_config()
    keywords = config.get('keywords', ['ontology', 'ontologies'])
    max_results = config.get('max_results', 50)
    output_dir = config.get('output_dir', './results')
    
    all_papers = []
    
    # 从 arXiv 获取
    print("正在从 arXiv 获取...")
    arxiv_papers = fetch_arxiv_papers(keywords, max_results)
    print(f"arXiv: 找到 {len(arxiv_papers)} 篇昨天的论文")
    all_papers.extend(arxiv_papers)
    
    # 从 PubMed 获取
    print("正在从 PubMed 获取...")
    pubmed_papers = fetch_pubmed_papers(keywords, max_results)
    print(f"PubMed: 找到 {len(pubmed_papers)} 篇昨天的论文")
    all_papers.extend(pubmed_papers)
    
    print(f"\n总计: {len(all_papers)} 篇论文")
    
    # 翻译为中文简介
    if all_papers:
        print("\n正在翻译论文标题和摘要...")
        all_papers = translate_papers(all_papers)
        print("翻译完成")
    
    # 保存结果
    json_path, md_path = save_results(all_papers, output_dir)
    print(f"\n结果已保存:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    
    # 输出摘要供 GitHub Actions 使用
    if all_papers:
        print(f"\n::notice::发现 {len(all_papers)} 篇 ontology 相关新论文（昨天）")
    
    return len(all_papers)


if __name__ == '__main__':
    main()
