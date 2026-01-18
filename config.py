"""
Configuration file for Google Drive Statement Organizer
"""

# Company patterns for classification
COMPANY_PATTERNS = {
    'chase': ['chase', 'jpmorgan', 'jpm', 'jp morgan', '4649', '64649'],
    'wells fargo': ['wells fargo', 'wells_fargo', 'wellsfargo', 'wells', 'wf', '5379'],
    'bank of america': ['bank of america', 'bank_of_america', 'bofa', 'boa', 'bankofamerica'],
    'capital one': ['capital one', 'capitalone', 'capone'],
    'american express': ['american express', 'american_express', 'amex', 'americanexpress', 'american-express'],
    'citi': ['citi', 'citibank', 'citigroup'],
    'us bank': ['us bank', 'usbank', 'usb'],
    'pnc': ['pnc', 'pnc bank'],

    'synchrony': ['synchrony', 'synchrony bank'],
    'discover': ['discover', 'discover card'],
    'barclays': ['barclays', 'barclaycard'],
    'fidelity': ['fidelity', 'fidelity investments'],
    'vanguard': ['vanguard', 'vanguard group'],
    'schwab': ['schwab', 'charles schwab', 'charlesschwab', '417', '624', '485', '608', '121', '625'],
    'etrade': ['etrade', 'e*trade', 'etrade'],
    'robinhood': ['robinhood', 'robinhood markets'],
    'coinbase': ['coinbase', 'coinbase pro'],
    'paypal': ['paypal', 'paypal credit'],
    'stripe': ['stripe'],
    'square': ['square', 'square cash'],
    'venmo': ['venmo'],
    'zelle': ['zelle'],
    'mint': ['mint', 'mint.com'],
    'quicken': ['quicken'],
    'turbotax': ['turbotax', 'turbo tax'],
    'h&r block': ['h&r block', 'hr block', 'hrblock'],
    'state farm': ['state farm', 'statefarm'],
    'geico': ['geico'],
    'progressive': ['progressive'],
    'allstate': ['allstate'],
    'liberty mutual': ['liberty mutual', 'libertymutual'],
    'farmers': ['farmers', 'farmers insurance'],
    'nationwide': ['nationwide'],
    'metlife': ['metlife'],
    'prudential': ['prudential'],
    'aetna': ['aetna'],
    'blue cross': ['blue cross', 'bluecross', 'blue cross blue shield'],
    'kaiser permanente': ['kaiser permanente', 'kaiserpermanente', 'kaiser'],
    'unitedhealth': ['unitedhealth', 'united health', 'unitedhealthcare'],
    'humana': ['humana'],
    'cigna': ['cigna'],
    'anthem': ['anthem'],
    'comcast': ['comcast', 'xfinity'],
    'verizon': ['verizon'],
    'at&t': ['at&t', 'att'],
    't-mobile': ['t-mobile', 'tmobile'],
    'sprint': ['sprint'],
    'spectrum': ['spectrum'],
    'cox': ['cox', 'cox communications'],
    'directv': ['directv', 'direct tv'],
    'dish': ['dish', 'dish network'],
    'netflix': ['netflix'],
    'hulu': ['hulu'],
    'disney+': ['disney+', 'disney plus'],
    'amazon prime': ['amazon prime', 'amazonprime'],
    'spotify': ['spotify'],
    'apple': ['apple', 'apple card', 'applecard'],
    'google': ['google', 'google pay', 'googlepay'],
    'microsoft': ['microsoft'],
    'adobe': ['adobe', 'adobe creative cloud'],
    'dropbox': ['dropbox'],
    'box': ['box'],
    'google drive': ['google drive', 'googledrive'],
    'onedrive': ['onedrive', 'one drive'],
    'icloud': ['icloud'],
    'github': ['github'],
    'gitlab': ['gitlab'],
    'bitbucket': ['bitbucket'],
    'slack': ['slack'],
    'zoom': ['zoom'],
    'teams': ['teams', 'microsoft teams'],
    'discord': ['discord'],
    'twitch': ['twitch'],
    'youtube': ['youtube', 'youtube premium'],
    'linkedin': ['linkedin', 'linkedin premium'],
    'indeed': ['indeed'],
    'glassdoor': ['glassdoor'],
    'monster': ['monster'],
    'careerbuilder': ['careerbuilder'],
    'ziprecruiter': ['ziprecruiter'],
    'dice': ['dice'],
    'stack overflow': ['stack overflow', 'stackoverflow'],
    'medium': ['medium'],
    'substack': ['substack'],
    'patreon': ['patreon'],
    'kickstarter': ['kickstarter'],
    'indiegogo': ['indiegogo'],
    'gofundme': ['gofundme'],
    'venmo': ['venmo'],
    'cash app': ['cash app', 'cashapp'],
    'zelle': ['zelle'],
    'western union': ['western union', 'westernunion'],
    'moneygram': ['moneygram'],
    'payoneer': ['payoneer'],
    'transferwise': ['transferwise', 'wise'],
    'revolut': ['revolut'],
    'chime': ['chime'],
    'ally': ['ally', 'ally bank'],
    'sofi': ['sofi', 'sofi bank'],
    'marcus': ['marcus', 'marcus by goldman sachs'],
    'goldman sachs': ['goldman sachs', 'goldmansachs'],
    'morgan stanley': ['morgan stanley', 'morganstanley'],
    'blackrock': ['blackrock'],
    'franklin templeton': ['franklin templeton', 'franklintempleton'],
    't. rowe price': ['t. rowe price', 'troweprice', 't rowe price'],
    'invesco': ['invesco'],
    'pimco': ['pimco'],
    'janus henderson': ['janus henderson', 'janushenderson'],
    'eaton vance': ['eaton vance', 'eatonvance'],
    'nuveen': ['nuveen'],
    'calvert': ['calvert'],
    'domini': ['domini'],
    'pax world': ['pax world', 'paxworld'],
    'green century': ['green century', 'greencentury'],
    'impax': ['impax'],
    'first trust': ['first trust', 'firsttrust'],
    'ishares': ['ishares'],
    'spdr': ['spdr', 'spdr etfs'],
    'invesco qqq': ['invesco qqq', 'qqq'],
    'ark invest': ['ark invest', 'arkinvest'],
    'cathie wood': ['cathie wood', 'cathiewood'],
    'berkshire hathaway': ['berkshire hathaway', 'berkshirehathaway'],
    'warren buffett': ['warren buffett', 'warrenbuffett'],
    'bill gates': ['bill gates', 'billgates'],
    'jeff bezos': ['jeff bezos', 'jeffbezos'],
    'elon musk': ['elon musk', 'elonmusk'],
    'mark zuckerberg': ['mark zuckerberg', 'markzuckerberg'],
    'larry page': ['larry page', 'larrypage'],
    'sergey brin': ['sergey brin', 'sergeybrin'],
    'sundar pichai': ['sundar pichai', 'sundarpichai'],
    'satya nadella': ['satya nadella', 'satyanadella'],
    'tim cook': ['tim cook', 'timcook'],
    'jim farley': ['jim farley', 'jimfarley'],
    'mary barra': ['mary barra', 'marybarra'],
    'jamie dimon': ['jamie dimon', 'jamiedimon'],
    'brian moynihan': ['brian moynihan', 'brianmoynihan'],
    'james gorman': ['james gorman', 'jamesgorman'],
    'david solomon': ['david solomon', 'davidsolomon'],
    'james dimon': ['james dimon', 'jamesdimon'],
    'lloyd blankfein': ['lloyd blankfein', 'lloydblankfein'],
    'john stumpf': ['john stumpf', 'johnstumpf'],
    'timothy sloan': ['timothy sloan', 'timothysloan'],
    'charles scharf': ['charles scharf', 'charlesscharf'],
    'brian t. moynihan': ['brian t. moynihan', 'briantmoynihan'],
    'andrew cecere': ['andrew cecere', 'andrewcecere'],
    'william demchak': ['william demchak', 'williamdemchak'],
    'richard davis': ['richard davis', 'richarddavis'],
    'andrew abele': ['andrew abele', 'andrewabele'],
    'kelly king': ['kelly king', 'kellyking'],
    'brian douglas': ['brian douglas', 'briandouglas'],
    'john turner': ['john turner', 'johnturner'],
    'david holt': ['david holt', 'davidholt'],
    'michael corbat': ['michael corbat', 'michaelcorbat'],
    'jane fraser': ['jane fraser', 'janefraser'],
    'steve forrest': ['steve forrest', 'steveforrest'],
    'john dugan': ['john dugan', 'johndugan'],
    'bill rogers': ['bill rogers', 'billrogers'],
    'kevin johnson': ['kevin johnson', 'kevinjohnson'],
    'dave lewis': ['dave lewis', 'davelewis'],
    'doug mcmillon': ['doug mcmillon', 'dougmcmillon'],
    'brian cornell': ['brian cornell', 'briancornell'],
    'marvin ellison': ['marvin ellison', 'marvinellison'],
    'todd vasos': ['todd vasos', 'toddvasos'],
    'brian goldner': ['brian goldner', 'briangoldner'],
    'ynon kreiz': ['ynon kreiz', 'ynonkreiz'],
    'bob iger': ['bob iger', 'bobiger'],
    'bob chapek': ['bob chapek', 'bobchapek'],
    'reed hastings': ['reed hastings', 'reedhastings'],
    'ted sarandos': ['ted sarandos', 'tedsarandos'],
    'jeff green': ['jeff green', 'jeffgreen'],
    'mark read': ['mark read', 'markread'],
    'john wren': ['john wren', 'johnwren'],
    'michael roth': ['michael roth', 'michaelroth'],
    'arthur sadoun': ['arthur sadoun', 'arthursadoun'],
    'yannick bollore': ['yannick bollore', 'yannickbollore'],
    'sir martin sorrell': ['sir martin sorrell', 'sirmartinsorrell'],
    'mark read': ['mark read', 'markread'],
    'john wren': ['john wren', 'johnwren'],
    'michael roth': ['michael roth', 'michaelroth'],
    'arthur sadoun': ['arthur sadoun', 'arthursadoun'],
    'yannick bollore': ['yannick bollore', 'yannickbollore'],
    'sir martin sorrell': ['sir martin sorrell', 'sirmartinsorrell'],
}

# Statement type patterns for classification
STATEMENT_PATTERNS = {
    'bank statement': [
        'bank statement', 'bank_statement', 'checking statement', 'savings statement', 
        'account statement', 'monthly statement', 'checking account',
        'savings account', 'deposit account', 'transaction history'
    ],
    'credit card statement': [
        'credit card statement', 'credit_card_statement', 'card statement', 'credit card bill',
        'card bill', 'credit statement', 'card account statement',
        'credit account', 'card account',
        # AmEx-specific patterns (date-named files are usually card statements)
        'xxxxx', 'xxxx-xxxxx', 'card ending', 'account ending'
    ],
    'investment statement': [
        'investment statement', 'investment_statement', 'portfolio statement', 'brokerage statement',
        'securities statement', 'investment account', 'portfolio account',
        'brokerage account', 'trading statement', 'investment summary',
        'portfolio summary', 'account summary'
    ],
    'loan statement': [
        'loan statement', 'loan_statement', 'mortgage statement', 'lending statement',
        'loan account', 'mortgage account', 'loan bill', 'mortgage bill',
        'payment statement', 'loan payment', 'mortgage payment',
        # Loan payoff patterns
        'paid in full', 'payoff', 'loan payoff', 'paid off', 'final payment'
    ],
    'insurance statement': [
        'insurance statement', 'insurance_statement', 'policy statement', 'insurance bill',
        'policy bill', 'insurance premium', 'policy premium',
        'coverage statement', 'benefits statement'
    ],
    'utility statement': [
        'utility statement', 'utility_statement', 'electric bill', 'gas bill', 'water bill',
        'internet bill', 'phone bill', 'cable bill', 'utility bill',
        'service statement', 'utility service', 'bill', 'detailed bill', 
        'monthly bill', 'service bill', 'telecom bill', 'wireless bill'
    ],
    'monthly statement': [
        'monthly statement', 'monthly_statement', 'statement', 'monthly bill',
        'account summary', 'billing statement'
    ],
    'tax statement': [
        'tax statement', 'tax document', 'tax form', 'tax return',
        'irs document', 'tax summary', 'tax information'
    ],
    'payroll statement': [
        'payroll statement', 'paycheck', 'pay stub', 'wage statement',
        'salary statement', 'earnings statement', 'pay statement'
    ],
    'retirement statement': [
        'retirement statement', '401k statement', 'ira statement',
        'pension statement', 'retirement account', '401k account',
        'ira account', 'pension account'
    ],
    'healthcare statement': [
        'healthcare statement', 'medical statement', 'health statement',
        'medical bill', 'health bill', 'medical expense', 'health expense'
    ],
    'subscription statement': [
        'subscription statement', 'subscription bill', 'membership statement',
        'membership bill', 'service subscription', 'recurring payment'
    ],
    'shipping statement': [
        'shipping statement', 'delivery statement', 'logistics statement',
        'freight statement', 'transportation statement'
    ],
    'legal statement': [
        'legal statement', 'legal document', 'legal bill', 'attorney statement',
        'law firm statement', 'legal expense'
    ],
    'accounting statement': [
        'accounting statement', 'bookkeeping statement', 'financial statement',
        'business statement', 'corporate statement', 'company statement'
    ]
}

# File extensions to process
SUPPORTED_EXTENSIONS = ['.pdf', '.PDF']

# Default folder names
DEFAULT_FOLDERS = {
    'monthly_statements': 'Monthly Statements',
    'statements_by_account': 'Statements by Account'
}

# Google Drive API settings
GOOGLE_DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
