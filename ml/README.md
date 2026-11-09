# Oryven Intent ML

O roteador local de intents existe para reduzir latência/custo e detectar rotas prováveis. Ele **não autoriza nem executa ações**. Toda ação executável continua passando por `ApprovalStore`.

## Dataset local

`datasets/oryven_intents_seed.csv` é o conjunto inicial criado para o produto. Formato: `text,label`.

## Kaggle

Para enriquecer linguagem natural/OOS, use apenas datasets cuja licença tenha sido revisada para uso comercial. O pipeline proposto é:

1. Baixar via Kaggle CLI (`kaggle datasets list -s clinc150`, depois `kaggle datasets download ...`).
2. Registrar origem, versão, licença, hash SHA-256 e data em `datasets/DATA_SOURCES.md`.
3. Extrair apenas exemplos compatíveis com a ontologia Oryven ou usá-los como OOS/robustez.
4. Nunca mapear automaticamente uma intenção Kaggle para uma ação de computador sem revisão humana.
5. Re-treinar `train_intent_router.py` e avaliar macro-F1, OOS recall, calibração e, principalmente, false-action rate.

O ATIS do Kaggle está sujeito às regras da competição, portanto não deve ser incorporado ao produto comercial sem validação jurídica/licença específica.
