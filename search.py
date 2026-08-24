import os
def search_dir(d):
    for root, dirs, files in os.walk(d):
        if '.venv' in root or '__pycache__' in root: continue
        for f in files:
            if not f.endswith('.py'): continue
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                try:
                    content = file.read()
                    if '"columns": []' in content or "'columns': []" in content or "build_semantic_table" in content:
                        print(f"Found in {path}")
                except Exception as e:
                    pass
search_dir("C:/Users/sanja/Downloads/tableau2pbi_workbench_v11_6_7_xml_powerquery_fixed/t2pbi_fix_v1166/backend")
