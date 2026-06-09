
import matplotlib.pyplot as plt
import seaborn as sns

'''Descriptive statistics function. Initial EDA analysis. Includes a description of the selected column. With histogram and box plot'''

def numerical_exploration(dataframe, column):
    print("DESCRIPTIVE STATISTICS \n")
    print(f"The minimum value for {column} is", dataframe[column].min())
    print(f"The maximum of {column} is", dataframe[column].max())
    print(f"The mean of {column} is", dataframe[column].mean())
    print(f"The median of {column} is", dataframe[column].median())
    print(f"-"*20)
    print(f"DESCRIBE :\n {dataframe[column].describe()} \n")

    print(f"-"*20)

#FIRST VISUALISATION: 

# Histogram (Distribution): 

    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1) #Two plots side by side
    sns.histplot(data=dataframe, x=column, kde=True) 
    plt.title(f'Histogram of {column}')


#Box Plot (Outliers and Dispersion):
    plt.subplot(1, 2, 2)
    sns.boxplot(data=dataframe, x=column)
    plt.title(f'Box plot of {column}')
    
    plt.tight_layout() 
    plt.show()




