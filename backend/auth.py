from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from database import get_db
import models, datetime

# Define o nome do Header que a automação deve enviar
API_KEY_NAME = "X-Service-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_service_account(
    api_key: str = Depends(api_key_header), 
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Token de serviço ausente."
        )

    # Busca o token no banco de dados
    account = db.query(models.ServiceAccount).filter(
        models.ServiceAccount.token == api_key,
        models.ServiceAccount.is_active == True
    ).first()

    # Validações: Existência e Expiração
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou conta inativa."
        )
    
    if account.expires_at < datetime.datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de serviço expirado."
        )

    return account