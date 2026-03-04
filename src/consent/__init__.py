"""DuckDuckGo autoconsent integration — 100+ CMP cookie consent auto-dismiss."""

import json
from pathlib import Path

_DIR = Path(__file__).parent
_IIFE: str | None = None
_BOOTSTRAP: str | None = None


def _load():
    global _IIFE, _BOOTSTRAP
    if _IIFE is not None:
        return

    _IIFE = (_DIR / "autoconsent.playwright.js").read_text()

    rules_raw = json.loads((_DIR / "rules.json").read_text())
    rules_payload = json.dumps({"autoconsent": rules_raw.get("autoconsent", [])})

    config = json.dumps({
        "enabled": True,
        "autoAction": "optIn",
        "disabledCmps": [],
        "enablePrehide": False,
        "enableCosmeticRules": True,
        "detectRetries": 20,
        "isMainWorld": True,
        "prehideTimeout": 2000,
        "enableFilterList": False,
        "logs": {"lifecycle": False, "rulesteps": False, "evals": False,
                 "errors": True, "messages": False},
    })

    # Self-contained bootstrap: sets up autoconsentSendMessage that auto-handles
    # init (responds with config+rules) and eval (executes and responds) messages.
    # No polling needed from Python — everything is handled in-page.
    _BOOTSTRAP = f"""(function(){{
  if(window.__autoconsentBootstrapped) return;
  window.__autoconsentBootstrapped=true;
  var CONFIG={config};
  var RULES={rules_payload};
  window.__autoconsentMessages=[];
  function _reply(msg){{
    var fn=function(){{
      if(window.autoconsentReceiveMessage){{
        window.autoconsentReceiveMessage(msg);
      }}else{{
        setTimeout(fn,10);
      }}
    }};
    setTimeout(fn,0);
  }}
  window.autoconsentSendMessage=async function(msg){{
    window.__autoconsentMessages.push(msg);
    if(msg.type==='init'){{
      _reply({{type:'initResp',config:CONFIG,rules:RULES}});
    }}else if(msg.type==='eval'){{
      try{{
        var r=eval(msg.code);
        if(r instanceof Promise) r=await r;
        _reply({{type:'evalResp',id:msg.id,result:!!r}});
      }}catch(e){{
        _reply({{type:'evalResp',id:msg.id,result:false}});
      }}
    }}
  }};
}})();"""


def get_consent_scripts() -> tuple[str, str]:
    """Return (bootstrap_js, iife_js) for injection into the page."""
    _load()
    return _BOOTSTRAP, _IIFE
