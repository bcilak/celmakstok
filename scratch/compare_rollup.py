"""
Çok seviyeli BOM maliyet roll-up düzeltmesinin ESKİ vs YENİ etkisini gösterir.

Canlı (gerçek) veritabanına bağlanır (SALT-OKUNUR; hiç yazma yapmaz), her BOM için
kök ürün maliyetini eski (hatalı, ara-adeti uygulamayan) ve yeni (düzeltilmiş)
hesaplamayla karşılaştırır. Böylece canlıya almadan ÖNCE sayısal etkiyi görürsün.

Kullanım (sunucuda, .env DATABASE_URL canlıyı gösterirken):
    venv/bin/python scratch/compare_rollup.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.utils.bom_utils import list_boms, get_bom_tree


def _old_total(node):
    """Düzeltmeden ÖNCEKİ kök/ara maliyet kuralını yeniden üretir.
    Yapraklar değişmedi (kendi adedini zaten uyguluyordu); ara (yarimamul) düğümler
    ESKİ kuralda kendi adedini UYGULAMIYOR (yalnızca çocukların toplamı)."""
    children = node.get('children') or []
    if not children:
        return float(node.get('total_cost') or 0.0)
    item_type = (node.get('item_type') or '')
    if item_type in ('hazir_parca', 'standart_parca'):
        # Bütün olarak fiyatlanan hazır parça (else dalı) — düzeltmeden etkilenmez
        return float(node.get('total_cost') or 0.0)
    return sum(_old_total(c) for c in children)


def main():
    app = create_app()
    with app.app_context():
        boms = list_boms(db)
        rows = []
        for b in boms:
            try:
                tree = get_bom_tree(b['bom_id'], db)
            except Exception as exc:
                print(f"  ! BOM #{b['bom_id']} okunamadı: {exc}")
                continue
            roots = tree.get('roots') or []
            if not roots:
                continue
            root = roots[0]
            new = float(root.get('total_cost') or 0.0)
            old = _old_total(root)
            rows.append((b['bom_id'], b.get('root_name') or '', old, new, new - old))

        rows.sort(key=lambda r: r[4], reverse=True)
        affected = [r for r in rows if abs(r[4]) > 0.5]

        print(f"\nToplam BOM: {len(rows)}  |  Çok-seviyeli etkilenen: {len(affected)}\n")
        if not affected:
            print("Hiçbir BOM etkilenmiyor (ara-adet hep 1). Maliyetler aynı kalıyor.")
            return

        print(f"{'BOM':>5} | {'ESKİ (TRY)':>15} | {'YENİ (TRY)':>15} | {'FARK (TRY)':>15} | {'%':>5} | Ürün")
        print("-" * 110)
        for bid, name, old, new, diff in affected:
            pct = (diff / old * 100) if old else 0.0
            print(f"{bid:>5} | {old:>15,.2f} | {new:>15,.2f} | {diff:>15,.2f} | {pct:>4.0f}% | {name[:45]}")

        toplam_eski = sum(r[2] for r in affected)
        toplam_yeni = sum(r[3] for r in affected)
        print("-" * 110)
        print(f"{'TOPLAM':>5} | {toplam_eski:>15,.2f} | {toplam_yeni:>15,.2f} | "
              f"{toplam_yeni - toplam_eski:>15,.2f} |")
        print("\nNot: Yalnızca ara montajında 1'den fazla adet bulunan ürünler etkilenir.")


if __name__ == '__main__':
    main()
