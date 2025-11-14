# migrations/versions/87ba381fb631_add_stock_to_products.py
from alembic import op
import sqlalchemy as sa

revision = '87ba381fb631'
down_revision = '91811e028187'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('products')]
    if 'stock' not in cols:
        with op.batch_alter_table('products') as batch_op:
            batch_op.add_column(sa.Column('stock', sa.Integer(), nullable=False, server_default='0'))
            # opcjonalnie: usunięcie domyślnej wartości po dodaniu
            batch_op.alter_column('stock', server_default=None)

def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns('products')]
    if 'stock' in cols:
        with op.batch_alter_table('products') as batch_op:
            batch_op.drop_column('stock')
