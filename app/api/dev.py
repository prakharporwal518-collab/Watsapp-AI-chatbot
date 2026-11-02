"""Local testing without WhatsApp: POST /dev/chat and a tiny browser chat UI at GET /dev.

Disabled automatically in production.
"""

from __future__ import annotations

import hashlib
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.whatsapp.parser import InboundMessage

router = APIRouter(prefix="/dev", tags=["dev"])


class ChatIn(BaseModel):
    user: str = Field(default="demo", max_length=40, description="Any name; maps to a fake phone number")
    text: str = Field(default="", max_length=4000)
    button_id: str | None = Field(default=None, max_length=256)
    name: str | None = Field(default="Student", max_length=60)


def _fake_wa_id(user: str) -> str:
    return "999" + str(int(hashlib.sha256(user.encode()).hexdigest(), 16))[:9]


def _guard(request: Request) -> None:
    s = request.app.state.container.settings
    if not s.dev_chat_enabled or s.environment == "production":
        raise HTTPException(status_code=404)


@router.post("/chat")
async def dev_chat(body: ChatIn, request: Request):
    _guard(request)
    msg = InboundMessage(
        message_id=f"dev.{uuid.uuid4().hex}", wa_id=_fake_wa_id(body.user), timestamp=int(time.time()),
        type="interactive" if body.button_id else "text", text=body.text, button_id=body.button_id,
        profile_name=body.name,
    )
    replies = await request.app.state.container.processor.process(msg, deliver=False)
    return {
        "replies": [
            {
                "kind": r.kind,
                "body": r.body,
                "buttons": [{"id": b.id, "title": b.title} for b in r.buttons],
                "rows": [{"id": x.id, "title": x.title, "description": x.description} for x in r.rows],
            }
            for r in replies
        ]
    }


@router.get("", response_class=HTMLResponse)
async def dev_ui(request: Request):
    _guard(request)
    return HTMLResponse(_PAGE)


_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tutor Dev Chat</title><style>
body{margin:0;font-family:system-ui,sans-serif;background:#efeae2;display:flex;flex-direction:column;height:100vh}
header{background:#075e54;color:#fff;padding:12px 16px;font-weight:600}
#log{flex:1;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:8px}
.m{max-width:80%;padding:8px 12px;border-radius:8px;white-space:pre-wrap;word-wrap:break-word;box-shadow:0 1px 1px #0002}
.u{align-self:flex-end;background:#d9fdd3}.b{align-self:flex-start;background:#fff}
.btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.btns button{border:1px solid #075e54;background:#fff;color:#075e54;border-radius:16px;padding:4px 10px;cursor:pointer}
form{display:flex;gap:8px;padding:12px;background:#f0f0f0}input{flex:1;padding:10px;border-radius:20px;border:1px solid #ccc}
code,pre{font-family:ui-monospace,monospace;background:#f4f4f4}
</style></head><body><header>📚 WhatsApp AI Tutor — dev chat</header><div id="log"></div>
<form id="f"><input id="t" placeholder="Type a message (try: hi, /help, explain binary search)" autocomplete="off"><button>Send</button></form>
<script>
const log=document.getElementById('log');const user='web-'+(localStorage.getItem('uid')||(()=>{const u=Math.random().toString(36).slice(2,8);localStorage.setItem('uid',u);return u})());
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function fmt(s){s=esc(s);s=s.replace(/```([\\s\\S]*?)```/g,(m,c)=>'<pre>'+c+'</pre>');return s.replace(/\\*([^*\\n]+)\\*/g,'<b>$1</b>').replace(/(^|\\s)_([^_\\n]+)_/g,'$1<i>$2</i>')}
function add(cls,html){const d=document.createElement('div');d.className='m '+cls;d.innerHTML=html;log.appendChild(d);log.scrollTop=1e9;return d}
async function send(text,button_id,label){add('u',esc(label||text));const r=await fetch('/dev/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user,text,button_id})});
const j=await r.json();for(const m of j.replies){const d=add('b',fmt(m.body||''));const opts=[...m.buttons,...m.rows];if(opts.length){const w=document.createElement('div');w.className='btns';
for(const o of opts){const b=document.createElement('button');b.textContent=o.title;b.title=o.description||'';b.onclick=()=>send(o.title,o.id,o.title);w.appendChild(b)}d.appendChild(w)}}}
document.getElementById('f').onsubmit=e=>{e.preventDefault();const t=document.getElementById('t');if(t.value.trim()){send(t.value);t.value=''}};
</script></body></html>"""
