"""Persist encrypted attachments in the database, including serverless deployments."""
from alembic import op
import sqlalchemy as sa

revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if 'anexos_conteudo' not in sa.inspect(bind).get_table_names():
        op.create_table('anexos_conteudo',sa.Column('id',sa.String(36),sa.ForeignKey('registros.id'),primary_key=True),sa.Column('encrypted',sa.LargeBinary,nullable=False))

def downgrade():
    op.drop_table('anexos_conteudo')
