import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def comparar_correlaciones(df, var1_name, var2_name, umbral_diferencia=0.1, mostrar_plot=True):
    """
    Calcula correlaciones Pearson y Spearman usando pandas, las compara y recomienda cuál usar.
    Pandas maneja automáticamente los valores NaN.
    
    Parámetros:
    -----------
    df : pandas DataFrame
        DataFrame que contiene las variables
    var1_name : str
        Nombre de la primera columna
    var2_name : str
        Nombre de la segunda columna
    umbral_diferencia : float, default=0.1
        Diferencia mínima entre coeficientes para considerar que hay discrepancia
    mostrar_plot : bool, default=True
        Si True, muestra un scatter plot de las variables
    
    Retorna:
    --------
    dict con:
        - 'pearson': coeficiente de Pearson
        - 'spearman': coeficiente de Spearman
        - 'diferencia': diferencia absoluta entre ambos
        - 'recomendacion': 'pearson' o 'spearman'
        - 'valor_recomendado': el valor del coeficiente recomendado
        - 'interpretacion': texto explicativo
    """
    
    # Verificar que las columnas existen
    if var1_name not in df.columns or var2_name not in df.columns:
        raise ValueError(f"Las columnas '{var1_name}' y/o '{var2_name}' no existen en el DataFrame")
    
    # Calcular correlaciones (pandas maneja NaN automáticamente)
    pearson_r = df[var1_name].corr(df[var2_name], method='pearson')
    spearman_r = df[var1_name].corr(df[var2_name], method='spearman')
    
    # Calcular diferencia absoluta
    diferencia = abs(pearson_r - spearman_r)
    
    # Contar valores válidos (sin NaN en ambas columnas)
    datos_validos = df[[var1_name, var2_name]].dropna()
    n_validos = len(datos_validos)
    n_total = len(df)
    
    # Decidir cuál recomendar
    if diferencia < umbral_diferencia:
        recomendacion = 'pearson'
        valor_recomendado = pearson_r
        interpretacion = f"""
✅ USAR PEARSON (r = {pearson_r:.3f})
   
   Razón: La diferencia entre Pearson y Spearman es pequeña ({diferencia:.3f}).
   Esto indica una relación aproximadamente lineal sin outliers significativos.
   
   Pearson: {pearson_r:.3f}
   Spearman: {spearman_r:.3f}
   
   Datos utilizados: {n_validos}/{n_total} ({n_validos/n_total*100:.1f}%)
        """
    else:
        recomendacion = 'spearman'
        valor_recomendado = spearman_r
        interpretacion = f"""
⚠️  USAR SPEARMAN (r = {spearman_r:.3f})
   
   Razón: Hay una diferencia notable entre Pearson y Spearman ({diferencia:.3f}).
   Esto sugiere presencia de outliers o relación no lineal.
   Spearman es más robusto en estos casos.
   
   Pearson: {pearson_r:.3f}
   Spearman: {spearman_r:.3f}
   
   Datos utilizados: {n_validos}/{n_total} ({n_validos/n_total*100:.1f}%)
        """
    
    # Interpretación de la fuerza
    fuerza_abs = abs(valor_recomendado)
    if fuerza_abs < 0.2:
        fuerza = "muy débil"
    elif fuerza_abs < 0.4:
        fuerza = "débil"
    elif fuerza_abs < 0.6:
        fuerza = "moderada"
    elif fuerza_abs < 0.8:
        fuerza = "fuerte"
    else:
        fuerza = "muy fuerte"
    
    direccion = "positiva" if valor_recomendado > 0 else "negativa"
    
    interpretacion += f"\n   Fuerza de la relación: {fuerza} {direccion}"
    
    # Mostrar scatter plot si se solicita
    if mostrar_plot:
        plt.figure(figsize=(10, 6))
        plt.scatter(datos_validos[var1_name], datos_validos[var2_name], 
                   alpha=0.5, edgecolors='k', linewidth=0.5)
        plt.xlabel(var1_name, fontsize=12)
        plt.ylabel(var2_name, fontsize=12)
        plt.title(f'Scatter Plot: {var1_name} vs {var2_name}\n' + 
                  f'Pearson: {pearson_r:.3f} | Spearman: {spearman_r:.3f} | Recomendado: {recomendacion.upper()}',
                  fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
    
    # Retornar resultados
    return {
        'pearson': pearson_r,
        'spearman': spearman_r,
        'diferencia': diferencia,
        'recomendacion': recomendacion,
        'valor_recomendado': valor_recomendado,
        'fuerza': fuerza,
        'direccion': direccion,
        'n_validos': n_validos,
        'n_total': n_total,
        'interpretacion': interpretacion
    }

def matriz_correlacion_visual(df, metodo='pearson', figsize=(15, 15), cmap='mako', 
                              annot=True, fmt='.2f', solo_triangulo=True):
    """
    Crea un heatmap visual de la matriz de correlación de un DataFrame.
    
    Parámetros:
    -----------
    df : pandas DataFrame
        DataFrame con las variables numéricas a correlacionar
    metodo : str, default='pearson'
        Método de correlación: 'pearson', 'spearman' o 'kendall'
    figsize : tuple, default=(15, 15)
        Tamaño de la figura (ancho, alto)
    cmap : str, default='mako'
        Paleta de colores (ejemplos: 'mako', 'coolwarm', 'viridis', 'RdBu_r')
    annot : bool, default=True
        Si True, muestra los valores numéricos en cada celda
    fmt : str, default='.2f'
        Formato de los números (ej: '.2f' = 2 decimales, '.3f' = 3 decimales)
    solo_triangulo : bool, default=True
        Si True, muestra solo el triángulo inferior (evita duplicados)
    
    Retorna:
    --------
    df_correlaciones : pandas DataFrame
        Matriz de correlación calculada
    """
    
    # Calcular la matriz de correlación
    df_correlaciones = df.corr(method=metodo, numeric_only=True)
    
    # Crear la figura
    plt.figure(figsize=figsize)
    
    # Crear máscara para el triángulo superior (si se solicita)
    if solo_triangulo:
        mask = np.triu(np.ones_like(df_correlaciones, dtype=bool))
    else:
        mask = None
    
    # Crear el heatmap
    sns.heatmap(df_correlaciones, 
                annot=annot, 
                fmt=fmt, 
                cmap=cmap, 
                vmax=1, 
                vmin=-1, 
                mask=mask,
                square=True,  # Celdas cuadradas
                linewidths=0.5,  # Líneas entre celdas
                cbar_kws={"shrink": 0.8})  # Tamaño de la barra de colores
    
    # Título
    plt.title(f'Matriz de Correlación ({metodo.capitalize()})', 
              fontsize=16, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.show()
    
    return df_correlaciones