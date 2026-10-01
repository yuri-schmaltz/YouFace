#!/usr/bin/env python3
"""
Script utilitário para limpar jobs stuck/orfãos do banco de dados do
YouFace. Roda localmente; não precisa de venv especial.

Uso:
    python scripts/clean_stuck_jobs.py [--dry-run] [--max-age-days N]

Por padrão, remove jobs com status 'processing' há mais de 1 dia (que
indica que o servidor foi morto durante o processamento) OU com
error_message contendo 'O servidor foi reiniciado'.

Argumentos:
    --dry-run          Mostra o que seria removido, sem deletar
    --max-age-days N   Idade máxima em dias para considerar um job
                       'stuck' (default: 1)

Sai com código 0 se OK, 1 se erro.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# Adiciona o repo root ao path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Defaults para o sys.path de imports acima
try:
    from youface.api.database import SessionLocal, JobModel
except ImportError as e:
    print(f"ERROR: cannot import youface.api.database: {e}")
    print("Hint: rode do repo root com PYTHONPATH=. ou via venv que tenha instalado o projeto.")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Limpa jobs stuck/orfãos do banco de dados do YouFace.")
    p.add_argument("--dry-run", action="store_true", help="Não deleta, só mostra o que seria removido")
    p.add_argument("--max-age-days", type=int, default=1, help="Idade máxima em dias para considerar stuck (default: 1)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_age_days)
        stuck = db.query(JobModel).filter(JobModel.status == "processing").filter(JobModel.date_updated < cutoff).all()
        orphan = db.query(JobModel).filter(JobModel.error_message.like("%servidor foi reiniciado%")).all()

        all_to_clean = list({j.id for j in stuck + orphan})
        print(f"Encontrados {len(all_to_clean)} jobs stuck/orfãos:")
        for jid in all_to_clean[:20]:  # mostra até 20
            print(f"  - {jid}")
        if len(all_to_clean) > 20:
            print(f"  ... e mais {len(all_to_clean) - 20}")

        if args.dry_run:
            print("\n[DRY RUN] Nada foi removido. Rode sem --dry-run para aplicar.")
            return 0

        if not all_to_clean:
            print("Nada a fazer.")
            return 0

        confirm = input(f"\nRemover {len(all_to_clean)} jobs? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelado.")
            return 0

        removed = 0
        for jid in all_to_clean:
            job = db.query(JobModel).filter(JobModel.id == jid).first()
            if job:
                db.delete(job)
                removed += 1
        db.commit()
        print(f"Removidos: {removed}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
