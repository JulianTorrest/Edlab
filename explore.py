import urllib.request, re, json, sys
url='https://taxonomy-prototype.pages.dev/demo/investigation-klim-b'
html=urllib.request.urlopen(url, timeout=20).read().decode('utf-8')
print('HTML length', len(html))
# find json in script tags
scripts=re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
for i,s in enumerate(scripts):
    if len(s.strip())>50:
        print(f'--- script {i} len {len(s)} ---')
        print(s[:4000])
        print(f'--- end script {i} ---\n')
