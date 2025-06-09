#!/usr/bin/env python3
"""
Boston 2014 Unsolved Homicides Statistical Analysis
Analyzes patterns and statistics from the Boston Police 2014 unsolved homicide cases
"""

import pandas as pd
import sys
import os
from datetime import datetime
import re

# Add the current directory to the path so we can import the cold case checker
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cold_case_cross_checker import ColdCaseCrossChecker

class BostonCrimeStatAnalyzer:
    def __init__(self):
        self.cases_data = None
        self.df = None
        
    def load_case_data(self):
        """Load Boston Police 2014 case data"""
        print("🔍 Loading Boston Police 2014 unsolved homicide data...")
        
        checker = ColdCaseCrossChecker()
        result = checker.scrape_boston_cases()
        print(f"📊 {result}")
        
        if not checker.boston_cases:
            print("❌ No case data available for analysis")
            return False
        
        # Convert to DataFrame for analysis
        cases_data = []
        for i, case in enumerate(checker.boston_cases, 1):
            cases_data.append({
                'Case_Number': i,
                'Victim': case.get('victim_name', 'Unknown'),
                'Age': case.get('age', 'Unknown'),
                'Gender': case.get('gender', 'Unknown'),
                'Date': case.get('date', 'Unknown'),
                'Location': case.get('location', 'Unknown'),
                'Description': case.get('description', 'No description available')
            })
        
        self.df = pd.DataFrame(cases_data)
        print(f"✅ Loaded {len(self.df)} cases for analysis")
        return True
    
    def clean_and_process_data(self):
        """Clean and process the data for analysis"""
        print("🧹 Cleaning and processing data...")
        
        # Clean age data
        def clean_age(age_str):
            if pd.isna(age_str) or age_str == 'Unknown':
                return None
            # Extract numeric age from strings like "25-year-old" or "25"
            age_match = re.search(r'(\d+)', str(age_str))
            if age_match:
                return int(age_match.group(1))
            return None
        
        self.df['Age_Numeric'] = self.df['Age'].apply(clean_age)
        
        # Clean gender data
        def clean_gender(gender_str):
            if pd.isna(gender_str) or gender_str == 'Unknown':
                return 'Unknown'
            gender_str = str(gender_str).lower()
            if 'male' in gender_str and 'female' not in gender_str:
                return 'Male'
            elif 'female' in gender_str:
                return 'Female'
            else:
                return 'Unknown'
        
        self.df['Gender_Clean'] = self.df['Gender'].apply(clean_gender)
        
        # Clean date data
        def clean_date(date_str):
            if pd.isna(date_str) or date_str == 'Unknown':
                return None
            try:
                # Try to parse various date formats
                date_str = str(date_str)
                # Remove common prefixes
                date_str = re.sub(r'^(on\s+|around\s+)', '', date_str, flags=re.IGNORECASE)
                
                # Try different date formats
                for fmt in ['%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%Y-%m-%d']:
                    try:
                        return pd.to_datetime(date_str, format=fmt)
                    except:
                        continue
                
                # Try pandas general parsing
                return pd.to_datetime(date_str, errors='coerce')
            except:
                return None
        
        self.df['Date_Parsed'] = self.df['Date'].apply(clean_date)
        
        # Extract month from dates
        self.df['Month'] = self.df['Date_Parsed'].dt.month
        self.df['Month_Name'] = self.df['Date_Parsed'].dt.strftime('%B')
        
        # Create age groups
        def age_group(age):
            if pd.isna(age):
                return 'Unknown'
            elif age < 18:
                return 'Under 18'
            elif age < 25:
                return '18-24'
            elif age < 35:
                return '25-34'
            elif age < 45:
                return '35-44'
            elif age < 55:
                return '45-54'
            elif age < 65:
                return '55-64'
            else:
                return '65+'
        
        self.df['Age_Group'] = self.df['Age_Numeric'].apply(age_group)
        
        print("✅ Data cleaning completed")
    
    def generate_basic_statistics(self):
        """Generate basic statistical overview"""
        print("\n📊 BASIC STATISTICS")
        print("=" * 50)
        
        total_cases = len(self.df)
        print(f"Total unsolved homicide cases: {total_cases}")
        
        # Gender distribution
        gender_counts = self.df['Gender_Clean'].value_counts()
        print(f"\n👥 Gender Distribution:")
        for gender, count in gender_counts.items():
            percentage = (count / total_cases) * 100
            print(f"  • {gender}: {count} ({percentage:.1f}%)")
        
        # Age statistics
        valid_ages = self.df['Age_Numeric'].dropna()
        if len(valid_ages) > 0:
            print(f"\n🎂 Age Statistics:")
            print(f"  • Average age: {valid_ages.mean():.1f} years")
            print(f"  • Median age: {valid_ages.median():.1f} years")
            print(f"  • Age range: {valid_ages.min():.0f} - {valid_ages.max():.0f} years")
            print(f"  • Cases with known age: {len(valid_ages)} ({(len(valid_ages)/total_cases)*100:.1f}%)")
        
        # Age group distribution
        age_group_counts = self.df['Age_Group'].value_counts()
        print(f"\n📈 Age Group Distribution:")
        for age_group, count in age_group_counts.items():
            percentage = (count / total_cases) * 100
            print(f"  • {age_group}: {count} ({percentage:.1f}%)")
    
    def analyze_temporal_patterns(self):
        """Analyze temporal patterns in the cases"""
        print("\n📅 TEMPORAL ANALYSIS")
        print("=" * 50)
        
        # Monthly distribution
        valid_dates = self.df.dropna(subset=['Month'])
        if len(valid_dates) > 0:
            month_counts = valid_dates['Month_Name'].value_counts()
            print(f"📆 Monthly Distribution:")
            for month, count in month_counts.items():
                percentage = (count / len(valid_dates)) * 100
                print(f"  • {month}: {count} ({percentage:.1f}%)")
            
            # Find peak months
            peak_month = month_counts.index[0]
            peak_count = month_counts.iloc[0]
            print(f"\n🔥 Peak month: {peak_month} with {peak_count} cases")
        else:
            print("❌ No valid date information available for temporal analysis")
    
    def analyze_location_patterns(self):
        """Analyze location patterns"""
        print("\n📍 LOCATION ANALYSIS")
        print("=" * 50)
        
        # Most common locations
        location_counts = self.df['Location'].value_counts()
        valid_locations = location_counts[location_counts.index != 'Unknown']
        
        print(f"🏘️ Most Common Locations:")
        for i, (location, count) in enumerate(valid_locations.head(10).items(), 1):
            percentage = (count / len(self.df)) * 100
            print(f"  {i:2d}. {location}: {count} ({percentage:.1f}%)")
        
        # Location diversity
        unique_locations = len(valid_locations)
        print(f"\n📊 Location Statistics:")
        print(f"  • Unique locations: {unique_locations}")
        print(f"  • Cases with known location: {len(self.df[self.df['Location'] != 'Unknown'])}")
        print(f"  • Average cases per location: {len(self.df) / unique_locations:.2f}")
    
    def analyze_demographic_patterns(self):
        """Analyze demographic patterns and correlations"""
        print("\n👥 DEMOGRAPHIC ANALYSIS")
        print("=" * 50)
        
        # Gender vs Age analysis
        gender_age_stats = self.df.groupby('Gender_Clean')['Age_Numeric'].agg(['count', 'mean', 'median']).round(1)
        print("🎯 Age by Gender:")
        for gender in gender_age_stats.index:
            stats = gender_age_stats.loc[gender]
            print(f"  • {gender}: {stats['count']} cases, avg age {stats['mean']}, median {stats['median']}")
        
        # Age group vs Gender cross-tabulation
        if len(self.df[self.df['Age_Group'] != 'Unknown']) > 0:
            crosstab = pd.crosstab(self.df['Age_Group'], self.df['Gender_Clean'], margins=True)
            print(f"\n📊 Age Group vs Gender Cross-tabulation:")
            print(crosstab)
    
    def identify_patterns_and_insights(self):
        """Identify key patterns and generate insights"""
        print("\n🔍 KEY INSIGHTS AND PATTERNS")
        print("=" * 50)
        
        insights = []
        
        # Gender patterns
        gender_counts = self.df['Gender_Clean'].value_counts()
        if 'Male' in gender_counts and 'Female' in gender_counts:
            male_pct = (gender_counts['Male'] / len(self.df)) * 100
            female_pct = (gender_counts['Female'] / len(self.df)) * 100
            if male_pct > female_pct * 2:
                insights.append(f"🔸 Male victims significantly outnumber female victims ({male_pct:.1f}% vs {female_pct:.1f}%)")
        
        # Age patterns
        valid_ages = self.df['Age_Numeric'].dropna()
        if len(valid_ages) > 0:
            young_adults = len(valid_ages[(valid_ages >= 18) & (valid_ages <= 35)])
            young_adult_pct = (young_adults / len(valid_ages)) * 100
            if young_adult_pct > 50:
                insights.append(f"🔸 Young adults (18-35) represent {young_adult_pct:.1f}% of victims with known ages")
        
        # Temporal patterns
        valid_dates = self.df.dropna(subset=['Month'])
        if len(valid_dates) > 0:
            month_counts = valid_dates['Month'].value_counts()
            summer_months = [6, 7, 8]  # June, July, August
            summer_cases = sum(month_counts.get(month, 0) for month in summer_months)
            summer_pct = (summer_cases / len(valid_dates)) * 100
            if summer_pct > 30:
                insights.append(f"🔸 Summer months show elevated activity with {summer_pct:.1f}% of cases")
        
        # Location patterns
        location_counts = self.df['Location'].value_counts()
        valid_locations = location_counts[location_counts.index != 'Unknown']
        if len(valid_locations) > 0:
            top_location_cases = valid_locations.iloc[0]
            if top_location_cases > 1:
                insights.append(f"🔸 Highest concentration: {valid_locations.index[0]} with {top_location_cases} cases")
        
        # Data quality insights
        known_age_pct = (len(self.df['Age_Numeric'].dropna()) / len(self.df)) * 100
        known_date_pct = (len(self.df.dropna(subset=['Date_Parsed'])) / len(self.df)) * 100
        
        insights.append(f"📊 Data completeness: {known_age_pct:.1f}% have known ages, {known_date_pct:.1f}% have known dates")
        
        if insights:
            for i, insight in enumerate(insights, 1):
                print(f"{i:2d}. {insight}")
        else:
            print("No significant patterns identified with available data.")
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        print("\n📋 SUMMARY REPORT")
        print("=" * 50)
        
        total_cases = len(self.df)
        print(f"Analysis of {total_cases} Boston Police 2014 unsolved homicide cases")
        print(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Key statistics
        male_count = len(self.df[self.df['Gender_Clean'] == 'Male'])
        female_count = len(self.df[self.df['Gender_Clean'] == 'Female'])
        known_ages = len(self.df['Age_Numeric'].dropna())
        avg_age = self.df['Age_Numeric'].mean()
        
        print(f"\n🎯 Key Statistics:")
        print(f"  • Male victims: {male_count} ({(male_count/total_cases)*100:.1f}%)")
        print(f"  • Female victims: {female_count} ({(female_count/total_cases)*100:.1f}%)")
        if known_ages > 0:
            print(f"  • Average victim age: {avg_age:.1f} years")
        print(f"  • Cases with complete age data: {known_ages} ({(known_ages/total_cases)*100:.1f}%)")
        
        # Most affected demographics
        if known_ages > 0:
            most_affected_age_group = self.df['Age_Group'].value_counts().index[0]
            most_affected_count = self.df['Age_Group'].value_counts().iloc[0]
            print(f"  • Most affected age group: {most_affected_age_group} ({most_affected_count} cases)")
    
    def save_analysis_to_file(self, filename='boston_2014_analysis_report.txt'):
        """Save the analysis results to a text file"""
        print(f"\n💾 Saving analysis report to {filename}...")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("BOSTON POLICE 2014 UNSOLVED HOMICIDES - STATISTICAL ANALYSIS REPORT\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total cases analyzed: {len(self.df)}\n\n")
                
                # Basic statistics
                f.write("BASIC STATISTICS\n")
                f.write("-" * 40 + "\n")
                gender_counts = self.df['Gender_Clean'].value_counts()
                for gender, count in gender_counts.items():
                    percentage = (count / len(self.df)) * 100
                    f.write(f"{gender}: {count} ({percentage:.1f}%)\n")
                
                # Age statistics
                valid_ages = self.df['Age_Numeric'].dropna()
                if len(valid_ages) > 0:
                    f.write(f"\nAge Statistics:\n")
                    f.write(f"Average age: {valid_ages.mean():.1f} years\n")
                    f.write(f"Median age: {valid_ages.median():.1f} years\n")
                    f.write(f"Age range: {valid_ages.min():.0f} - {valid_ages.max():.0f} years\n")
                
                # Age groups
                f.write(f"\nAge Group Distribution:\n")
                age_group_counts = self.df['Age_Group'].value_counts()
                for age_group, count in age_group_counts.items():
                    percentage = (count / len(self.df)) * 100
                    f.write(f"{age_group}: {count} ({percentage:.1f}%)\n")
                
                # Top locations
                f.write(f"\nTop 10 Locations:\n")
                location_counts = self.df['Location'].value_counts()
                valid_locations = location_counts[location_counts.index != 'Unknown']
                for i, (location, count) in enumerate(valid_locations.head(10).items(), 1):
                    percentage = (count / len(self.df)) * 100
                    f.write(f"{i:2d}. {location}: {count} ({percentage:.1f}%)\n")
                
                # Raw data summary
                f.write(f"\nRAW DATA SAMPLE (First 10 cases):\n")
                f.write("-" * 40 + "\n")
                for _, row in self.df.head(10).iterrows():
                    f.write(f"Case {row['Case_Number']}: {row['Victim']}, {row['Age']}, {row['Gender']}, {row['Date']}, {row['Location']}\n")
            
            print(f"✅ Analysis report saved successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return False
    
    def run_complete_analysis(self):
        """Run the complete statistical analysis"""
        print("🔬 BOSTON 2014 UNSOLVED HOMICIDES - STATISTICAL ANALYSIS")
        print("=" * 70)
        print("Analyzing patterns, demographics, and trends in unsolved homicide cases")
        print()
        
        try:
            # Load data
            if not self.load_case_data():
                return False
            
            # Clean and process data
            self.clean_and_process_data()
            
            # Run all analyses
            self.generate_basic_statistics()
            self.analyze_temporal_patterns()
            self.analyze_location_patterns()
            self.analyze_demographic_patterns()
            self.identify_patterns_and_insights()
            self.generate_summary_report()
            
            # Save report
            self.save_analysis_to_file()
            
            print("\n✅ Statistical analysis completed successfully!")
            print("📄 Detailed report saved as 'boston_2014_analysis_report.txt'")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function to run the statistical analysis"""
    analyzer = BostonCrimeStatAnalyzer()
    analyzer.run_complete_analysis()

if __name__ == "__main__":
    main()
