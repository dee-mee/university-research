import os
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'research_portal.settings')
django.setup()

from research.models import ResearchCategory, ResearchItem

# Categories with descriptions
CATEGORIES = {
    "Machine Learning": "Research in machine learning algorithms, neural networks, and deep learning applications",
    "Data Science": "Studies in data analysis, visualization, and statistical modeling",
    "Artificial Intelligence": "Research in AI systems, cognitive computing, and intelligent agents",
    "Computer Vision": "Studies in image processing, pattern recognition, and visual computing",
    "Natural Language Processing": "Research in text analysis, language models, and speech recognition",
    "Robotics": "Studies in robotic systems, automation, and control systems",
    "Cybersecurity": "Research in network security, cryptography, and threat detection",
    "Blockchain": "Studies in distributed ledger technology and cryptocurrency applications",
    "Cloud Computing": "Research in cloud architecture, distributed systems, and virtualization",
    "Internet of Things": "Studies in IoT devices, sensor networks, and smart systems"
}

# Sample research titles with variations
TITLE_TEMPLATES = [
    "Advanced {topic} for {application}",
    "Deep Learning Approaches in {field}",
    "Novel {method} in {domain}",
    "Machine Learning Applications for {application}",
    "Data-Driven {solution} in {industry}",
    "Intelligent {system} for {purpose}",
    "Automated {process} using {technology}",
    "Secure {method} for {domain}",
    "Modern {solution} in {industry}",
    "Real-time {process} of {domain}"
]

# Topics and applications for title generation
TOPICS = ["Neural Networks", "Data Analysis", "Pattern Recognition", "System Design", "Algorithm Development"]
APPLICATIONS = ["Healthcare", "Finance", "Manufacturing", "Education", "Transportation"]
FIELDS = ["Medical Imaging", "Financial Markets", "Industrial Automation", "Educational Technology", "Smart Cities"]
METHODS = ["Classification", "Regression", "Clustering", "Optimization", "Simulation"]
DOMAINS = ["Computer Vision", "Natural Language Processing", "Robotics", "Cybersecurity", "IoT"]

# Sample authors with affiliations
AUTHORS = [
    "John Smith (MIT), Jane Doe (Stanford)",
    "Michael Johnson (Harvard), Sarah Williams (UC Berkeley)",
    "David Brown (Oxford), Emily Davis (Cambridge)",
    "Robert Wilson (ETH Zurich), Jennifer Taylor (EPFL)",
    "William Anderson (UCLA), Jessica Thomas (UCSD)",
    "James Martinez (UT Austin), Amanda Garcia (Georgia Tech)",
    "Daniel Robinson (Carnegie Mellon), Michelle Lee (UIUC)",
    "Christopher Walker (Princeton), Stephanie Hall (Yale)",
    "Matthew Young (Columbia), Rebecca Allen (NYU)",
    "Andrew King (Imperial College), Laura Scott (UCL)"
]

def generate_unique_title():
    """Generate a unique research title using templates and random components"""
    max_attempts = 10
    for _ in range(max_attempts):
        template = random.choice(TITLE_TEMPLATES)
        replacements = {
            'topic': lambda: random.choice(TOPICS),
            'application': lambda: random.choice(APPLICATIONS),
            'field': lambda: random.choice(FIELDS),
            'method': lambda: random.choice(METHODS),
            'domain': lambda: random.choice(DOMAINS),
            'solution': lambda: random.choice(["Analysis", "System", "Framework", "Model"]),
            'industry': lambda: random.choice(["Healthcare", "Finance", "Manufacturing", "Education"]),
            'system': lambda: random.choice(["Analysis", "System", "Framework", "Model"]),
            'purpose': lambda: random.choice(["Healthcare", "Finance", "Manufacturing", "Education"]),
            'process': lambda: random.choice(["Analysis", "Processing", "Detection", "Monitoring"]),
            'technology': lambda: random.choice(["AI", "ML", "DL", "IoT"])
        }
        
        format_dict = {}
        for key, value_func in replacements.items():
            if "{" + key + "}" in template:
                format_dict[key] = value_func()
        
        title = template.format(**format_dict)
        
        # Check if title already exists
        if not ResearchItem.objects.filter(title=title).exists():
            return title
    
    raise ValueError("Failed to generate a unique title after multiple attempts")

def create_categories():
    """Create research categories if they don't exist"""
    created_categories = []
    for category_name, description in CATEGORIES.items():
        try:
            category, created = ResearchCategory.objects.get_or_create(
                name=category_name,
                defaults={'description': description}
            )
            if created:
                print(f"Created category: {category_name}")
            created_categories.append(category)
        except IntegrityError:
            print(f"Category {category_name} already exists, skipping...")
        except Exception as e:
            print(f"Error creating category {category_name}: {str(e)}")
    
    return created_categories

def create_research_item(category, year):
    """Create a single research item with proper error handling"""
    try:
        title = generate_unique_title()
        authors = random.choice(AUTHORS)
        
        # Generate a random publication date within the year
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        random_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        
        research_item = ResearchItem.objects.create(
            title=title,
            category=category,
            year=year,
            description=f"This research paper explores {title.lower()}. "
                       f"Published in {year}, it presents novel findings in the field of {category.name}. "
                       f"The study was conducted by {authors} and contributes to the advancement of {category.name.lower()}.",
            authors=authors,
            publication_date=random_date,
            is_published=True
        )
        return research_item
    except IntegrityError:
        print(f"Duplicate title found: {title}, skipping...")
        return None
    except ValidationError as e:
        print(f"Validation error for {title}: {str(e)}")
        return None
    except Exception as e:
        print(f"Error creating research item: {str(e)}")
        return None

@transaction.atomic
def create_dummy_data():
    """Main function to create dummy research data"""
    print("Starting dummy data creation...")
    
    try:
        # Create categories
        categories = create_categories()
        if not categories:
            raise ValueError("No categories were created or found")
        
        # Create research items
        total_created = 0
        for year in range(2018, 2024):  # Data from 2018 to 2023
            print(f"\nCreating items for year {year}...")
            year_created = 0
            
            for _ in range(5):  # 5 items per year
                category = random.choice(categories)
                research_item = create_research_item(category, year)
                
                if research_item:
                    year_created += 1
                    total_created += 1
            
            print(f"Created {year_created} items for {year}")
        
        print(f"\nDummy data creation completed successfully!")
        print(f"Total items created: {total_created}")
        print(f"Categories used: {', '.join(c.name for c in categories)}")
        
    except Exception as e:
        print(f"An error occurred during data creation: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        create_dummy_data()
    except Exception as e:
        print(f"Script failed: {str(e)}")
        exit(1) 