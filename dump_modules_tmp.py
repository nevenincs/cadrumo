import json, sys
from cadrumo.domain.calculations.registry.authority import bundled_authority
bundled_authority()
print(json.dumps(sorted(n for n in sys.modules if n.startswith("cadrumo"))))
