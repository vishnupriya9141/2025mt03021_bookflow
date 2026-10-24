"""Static packaging checks; does not claim container or cluster validation."""
from pathlib import Path
import json
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    stream = (ROOT / 'k8s/workloads.yaml').read_text(encoding='utf-8')
    resources = [json.loads(item) for item in stream.split('\n---\n')]
    assert len(resources) == 6
    for name in ['inventory', 'orders']:
        deployment = next(r for r in resources if r['kind'] == 'Deployment' and r['metadata']['name'] == name)
        service = next(r for r in resources if r['kind'] == 'Service' and r['metadata']['name'] == name)
        spec = deployment['spec']
        assert spec['replicas'] == 1 and spec['strategy']['type'] == 'Recreate'
        assert service['spec']['selector'] == spec['template']['metadata']['labels']
        container = spec['template']['spec']['containers'][0]
        assert container['image'] == f'bookflow-{name}:1.0'
        assert container['readinessProbe']['httpGet']['path'] == '/health/ready'
        assert container['volumeMounts'][0]['mountPath'] == '/data'
    print('Manifest JSON syntax and internal references: OK (not Kubernetes server validation)')
    postman = json.loads((ROOT / 'postman/2025m203021_BookFlow.postman_collection.json').read_text(encoding='utf-8'))
    assert len(postman['item']) == 9
    assert all(item['event'] for item in postman['item'])
    print('Postman collection structure: OK (not a Postman runtime execution)')
    with zipfile.ZipFile(ROOT / '2025m203021_BookFlow_Report.docx') as doc:
        xml = ET.fromstring(doc.read('word/document.xml'))
        text = ''.join(xml.itertext())
        assert 'Vattikunta Vishnu Priya' in text and '2025m203021' in text
        assert len([n for n in doc.namelist() if n.startswith('word/media/')]) == 3
    print('DOCX identity, XML and three embedded figures: OK')
    with zipfile.ZipFile(ROOT / '2025m203021_BookFlow.zip') as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert not any('/.git/' in name or '/__pycache__/' in name for name in names)
        assert sum(name.endswith('.bundle') for name in names) == 2
        for service in ['order-service','inventory-service']:
            assert any(name.endswith(f'{service}/app.py') for name in names)
            assert any(name.endswith(f'{service}/.github/workflows/ci.yml') for name in names)
    print('ZIP integrity, independent repo bundles, source and CI files: OK')


if __name__ == '__main__':
    main()
