# Sistema de Alarme por Movimento (Sem IA)

Projeto de Visão Computacional para detectar movimento em tempo real usando técnicas clássicas (subtração de fundo e contornos), sem uso de inteligência artificial.

## Recursos

- Detecção de movimento com OpenCV (MOG2 + operações morfológicas)
- Alarme sonoro no Windows com `winsound`
- Registro de evidência em imagem (`captures/`)
- Controle em tempo real por teclado

## Requisitos

- Python 3.10+
- Webcam conectada

Instalação de dependências:

```bash
pip install -r requirements.txt
```

## Execução

```bash
python alarm_movimento.py
```

Parâmetros opcionais:

```bash
python alarm_movimento.py --camera 0 --min-area 1500 --cooldown 5 --frames-confirmacao 6
```

## Teclas de atalho durante execução

- `q`: sair
- `a`: armar/desarmar o alarme
- `r`: reiniciar modelo de fundo (recalibrar)

## Como funciona (sem IA)

1. Cada frame é convertido para escala de cinza.
2. É aplicada subtração de fundo para separar regiões em movimento.
3. O resultado passa por limiarização e filtros morfológicos.
4. Contornos maiores que uma área mínima são considerados movimento válido.
5. Quando movimento persiste por alguns frames consecutivos, o alarme dispara.

## Estrutura gerada em execução

- `captures/`: imagens salvas quando houver disparo

## Observações

- Ajuste `--min-area` para reduzir falsos positivos.
- Use ambiente com iluminação estável para melhor resultado.
