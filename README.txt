AGROVISION ANGOLA — EXPERIÊNCIA GUIADA + MOTOR NDVI SENTINEL-2
====================================================

O QUE FOI ACTUALIZADO
--------------------
0. A interface inclui agora um resumo legível do estado dos registos, próximos passos e guia inicial de utilização.
0. Cada módulo apresenta instruções de utilização, sequência de acções e limitações importantes.
1. Gestão de propriedades, talhões, polígonos e campanhas foi preservada.
2. Monitorização meteorológica NASA POWER: temperatura, precipitação,
   humidade relativa, vento e radiação, com histórico gráfico.
3. Estimativas de humidade superficial e radicular NASA POWER / SMAP L4,
   com gráfico histórico. São dados modelados em grelha regional (~9 km),
   não medições directas no terreno.
4. Motor geoespacial NDVI com Sentinel-2 L2A, bandas B04 e B08 (10 m) e
   banda SCL para excluir píxeis inválidos, sombras e nuvens.
5. Estatísticas reais por polígono: média, mínimo, máximo, píxeis válidos,
   cobertura válida e percentagem por classes NDVI.
6. Pré-visualização classificada do raster calculado no mapa.
7. Comparação de duas datas Sentinel-2, com variação da média NDVI e um
   sinal de redução significativa para orientar uma inspecção.
8. Simulador de rotação preservado, utilizando o histórico de campanhas,
   perfil de solo, pH, água e contexto climático carregado.
9. Alertas de inspecção combinam sinais climáticos regionais, observações
   de campo e redução média NDVI quando existe comparação disponível.

COMO EXECUTAR NO WINDOWS
------------------------
1. Extraia a pasta AgroVision_Angola.
2. Instale Python 3.10 a 3.12 (64 bits) e certifique-se de que o Python está
   disponível no terminal. O Rasterio pode não ter roda compatível com todas
   as versões mais recentes do Python.
3. Faça duplo clique em start_windows.bat. Na primeira execução, o script
   cria um ambiente virtual e instala as dependências.
4. Aguarde a mensagem do servidor e abra no navegador:
   http://127.0.0.1:8000
5. Para parar o servidor, volte à janela preta e carregue Ctrl+C.

LINUX / macOS
-------------
Execute no terminal:
  chmod +x start_linux_mac.sh
  ./start_linux_mac.sh
Depois abra http://127.0.0.1:8000.

ANÁLISE NDVI
-----------
1. Abra Mapa inteligente e desenhe o limite real do talhão (mínimo 3 pontos).
2. Guarde o talhão e abra Monitorização.
3. Seleccione esse talhão.
4. Escolha a data pretendida e carregue em “Calcular NDVI real”.
5. O servidor pesquisa cenas Sentinel-2 L2A num intervalo de ±15 dias,
   dentro do limite de nuvens seleccionado. A data real de aquisição aparece
   nos resultados. Se não existir cena adequada, a aplicação informa isso.
6. Para comparar, escolha também a data anterior e carregue “Comparar datas”.

FONTES E ACESSO
---------------
- Sentinel-2 L2A: Microsoft Planetary Computer STAC API (catálogo público)
  e API pública de assinatura temporária de URLs de dados. Não requer chave
  de API para o uso básico, mas exige ligação à Internet e está sujeito a
  limites de utilização do serviço.
- NASA POWER: dados meteorológicos diários e parâmetros SFMC/RZMC usados
  como estimativas modeladas de humidade do solo.
- NASA GIBS: camadas cartográficas MODIS NDVI, SMAP e GPM para visualização.
- Esri World Imagery / OpenStreetMap: cartografia de referência.

LIMITAÇÕES IMPORTANTES
----------------------
- A análise NDVI é baseada em dados científicos Sentinel-2 L2A, não na cor
  de mosaicos GIBS. São usados os píxeis cujo centro cai dentro do polígono;
  a média não é ponderada pela fracção de área de píxeis de fronteira.
- A máscara SCL exclui classes 0, 1, 3, 8, 9, 10 e 11. A disponibilidade
  e qualidade da cena variam com a data, cobertura de nuvens e catálogo.
- A comparação temporal calcula a diferença entre médias do talhão. Não
  calcula ainda mapas de diferença pixel-a-pixel nem identifica a causa
  agronómica de uma alteração.
- A camada MODIS tem resolução aproximada de 250 m; é apenas uma referência
  visual regional e não é usada para as estatísticas Sentinel-2.
- NASA POWER / SMAP L4 tem resolução regional aproximada de 9 km. Talhões
  pequenos podem partilhar o mesmo valor de grelha. Não é sensor no solo.
- Alertas de anomalia são sinais de triagem, não diagnósticos de pragas,
  doenças ou défice hídrico.
- A rotação de culturas usa regras agronómicas gerais e os registos inseridos.
  Não é modelo calibrado para variedades, solos e condições locais de Angola.
- A aplicação ainda usa LocalStorage: os dados ficam neste navegador e
  neste computador. Não há sincronização entre dispositivos.
- Os talhões e campanhas pré-carregados são dados demonstrativos. Apague-os
  ou substitua-os pelos dados reais antes de utilizar operacionalmente.

TESTES EXECUTADOS NO DESENVOLVIMENTO
------------------------------------
- 4 testes automatizados passaram: fórmula NDVI e estatísticas, exclusão de
  píxel por máscara de qualidade, exclusão de denominador zero e validação
  do polígono.
- Sintaxe JavaScript verificada com node --check.
- Sintaxe Python verificada com py_compile.
- A consulta remota ao Planetary Computer não pôde ser executada neste
  ambiente de desenvolvimento por indisponibilidade de resolução DNS/rede.
  A primeira análise real deve ser feita com Internet activa no teu PC.

ORIENTAÇÃO PARA O UTILIZADOR
----------------------------
- Visão geral: mostra totais reais dos registos locais, qualidade/completude dos
  dados básicos e uma próxima acção sugerida. Não confunde completude com saúde
  agronómica da cultura.
- Primeiros passos: configurar localização, registar talhões, desenhar limites
  e só depois executar análises.
- Cada módulo explica para que serve, como utilizar e que limitações considerar.
- As recomendações são orientações de verificação. Não são diagnósticos automáticos.

PRESERVAÇÃO DE CONFIGURAÇÕES
----------------------------
- Os identificadores, nomes de armazenamento, configurações e valores de token
  existentes foram mantidos sem alteração nesta actualização.
- O token presente em config.js continua identificado no próprio ficheiro como
  marcador fictício de demonstração, não como credencial válida.

FICHEIROS PRINCIPAIS
--------------------
index.html / styles.css / app.js — aplicação web.
server.py — API e processamento geoespacial Sentinel-2.
requirements.txt — dependências Python.
start_windows.bat — instalação e arranque no Windows.
start_linux_mac.sh — instalação e arranque em Linux/macOS.
tests/test_ndvi.py — testes dos cálculos NDVI.
config.js — mantém apenas o marcador de token fictício anterior; não é usado
pela API Sentinel-2 nem deve receber credenciais reais.





