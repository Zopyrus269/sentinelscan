from apps.backend.agent import orchestrator

def test_cvss_phase_runs_after_evidence(monkeypatch, tmp_path):
    calls=[]
    def fake_dispatch(name,args):
        calls.append(name)
        if name=='dns_lookup': return {'A':['203.0.113.1'],'AAAA':[],'MX':[],'NS':[],'TXT':[],'CNAME':[]}
        if name=='http_headers': return {'missing_headers':['Content-Security-Policy'],'present_headers':{}}
        if name=='cookie_analysis': return {'total_cookies_found':0,'vulnerable_cookies_count':0,'cookies':[]}
        if name=='reverse_dns_lookup': return {'hostnames':[]}
        if name=='calculate_cvss': return {'base_score':5.3,'severity':'MEDIUM','vector':'CVSS:3.1/test'}
        return {}
    monkeypatch.setattr(orchestrator,'dispatch_tool',fake_dispatch)
    monkeypatch.setattr(orchestrator,'generate_report',lambda *a,**k:{'pdf_path':str(tmp_path/'r.pdf'),'json_path':str(tmp_path/'r.json')})
    result=orchestrator.run_scan('example.com')
    assert result['status']=='complete'
    first_cvss=calls.index('calculate_cvss')
    assert all(x!='calculate_cvss' for x in calls[:first_cvss])
    assert calls[-1]=='calculate_cvss'
