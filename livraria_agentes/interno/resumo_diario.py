"""Mantido por compatibilidade: o resumo diário agora é a rotina da manhã.

    python -m livraria_agentes.interno.rotinas manha [--whatsapp]
"""

from __future__ import annotations

import sys

from .rotinas import main

if __name__ == "__main__":
    sys.argv.insert(1, "manha")
    main()
