import json
import os
import argparse

# ANSI escape codes for colors
COLOR_BLUE = "\033[94m"   # Bright Blue
COLOR_GREEN = "\033[92m"  # Bright Green
COLOR_YELLOW = "\033[93m" # Bright Yellow
COLOR_ORANGE = "\033[33m" # Orange
COLOR_RED = "\033[91m"    # Bright Red
COLOR_PURPLE = "\033[95m" # Bright Magenta/Purple
COLOR_CYAN = "\033[96m"   # Bright Cyan

COLOR_RESET = "\033[0m"
BOLD = "\033[1m"
RESET_BOLD = "\033[22m" # Resets bold/light effect

# Ordered list of colors for "rainbow" progression (starting with Blue)
RAINBOW_COLORS = [
    COLOR_BLUE,
    COLOR_GREEN,
    COLOR_YELLOW,
    COLOR_ORANGE,
    COLOR_RED,
    COLOR_PURPLE,
    COLOR_CYAN
]

def get_color_for_depth(depth):
    """Returns a color from the rainbow palette based on depth, cycling through them."""
    return RAINBOW_COLORS[depth % len(RAINBOW_COLORS)]

def print_json_tree_colored(node, indent_flags, label=None):
    """
    Recursively prints a color-coded tree structure from a JSON node.
    indent_flags: A list of booleans indicating if the parent level was the last element.
                  Used to draw vertical lines.
    label: The key/index from the parent, used for printing.
    """
    # Calculate the indentation string based on indent_flags (vertical lines)
    indent_str = "".join(["    " if flag else "│   " for flag in indent_flags[:-1]])
    # Determine the branch prefix for the current item (├── or └──)
    prefix = "└── " if (indent_flags and indent_flags[-1]) else "├── "

    if isinstance(node, dict):
        # Special handling for the root profile node (identified by its structure and being at top level)
        if "profile_url" in node and "scraped_affiliates_table_data" in node and not indent_flags:
            print(f"{COLOR_BLUE}Profile: {node['profile_url']}{COLOR_RESET} (Depth: {node['depth']})")
            items = list(node.items())
            # Filter out None or empty string values before iterating and printing
            filtered_items = [(k, v) for k, v in items if v is not None and v != ""]
            for i, (key, value) in enumerate(filtered_items):
                # Skip internal/already printed keys
                if key in ["profile_url", "depth", "status"]: continue
                is_last_item = (i == len(filtered_items) - 1)
                print_json_tree_colored(value, indent_flags + [is_last_item], label=key)
        
        # Special handling for affiliate rows (they have 'Name' and 'nested_affiliates_data')
        elif "Name" in node and "nested_affiliates_data" in node:
            if label: # If this is a labeled item (e.g., from a list of affiliates)
                print(f"{indent_str}{prefix}{COLOR_BLUE}{label}: Name: {node['Name']}{COLOR_RESET}")
            else: # If it's a direct child of another node that doesn't provide a label
                print(f"{indent_str}{prefix}{COLOR_BLUE}Name: {node['Name']}{COLOR_RESET}")
            
            items = list(node.items())
            # Filter out None or empty string values before iterating and printing
            filtered_items = [(k, v) for k, v in items if v is not None and v != ""]
            for i, (key, value) in enumerate(filtered_items):
                # Skip 'Name' as it's already printed, and 'profile_url' and 'depth' are not expected here
                if key in ["Name", "profile_url", "depth", "status"]: continue
                is_last_item = (i == len(filtered_items) - 1)
                print_json_tree_colored(value, indent_flags + [is_last_item], label=key)

        # Generic dictionary handling
        else:
            if label:
                print(f"{indent_str}{prefix}{COLOR_GREEN}{label}:{{}}{COLOR_RESET}") # Indicate it's a dictionary
            else:
                print(f"{indent_str}{prefix}{COLOR_GREEN}{{}}{COLOR_RESET}") # Indicate it's a dictionary
            
            items = list(node.items())
            # Filter out None or empty string values before iterating and printing
            filtered_items = [(k, v) for k, v in items if v is not None and v != ""]
            for i, (key, value) in enumerate(filtered_items):
                is_last_item = (i == len(filtered_items) - 1)
                print_json_tree_colored(value, indent_flags + [is_last_item], label=key)

    elif isinstance(node, list):
        if label:
            print(f"{indent_str}{prefix}{COLOR_BLUE}{label}: [{len(node)} items]{COLOR_RESET}")
        else:
            print(f"{indent_str}{prefix}{COLOR_BLUE}List: [{len(node)} items]{COLOR_RESET}")

        # Filter out None or empty string values from the list
        filtered_node = [item for item in node if item is not None and item != ""]

        if not filtered_node: # Check filtered list for emptiness
            # Special case for empty lists (after filtering)
            sub_indent_str = "".join(["    " if flag else "│   " for flag in indent_flags])
            print(f"{sub_indent_str}└── {COLOR_ORANGE}Empty{COLOR_RESET}")

        for i, item in enumerate(filtered_node):
            is_last_item = (i == len(filtered_node) - 1)
            # For list items, label is typically their index if parent had a label, otherwise None
            print_json_tree_colored(item, indent_flags + [is_last_item], label=f"[{i}]" if label else None)

    else: # Primitive types: str, int, float, bool, None
        if node is None or node == "": # Do not print if node is None or empty string
            return
        
        color = COLOR_GREEN # Default color for data values
        if label and label.endswith("_link"):
            color = COLOR_YELLOW # Specific color for links
        elif label == "status" and node == "already_visited": 
            color = COLOR_ORANGE # Specific color for 'already_visited' status
        
        if label:
            print(f"{indent_str}{prefix}{color}{label}: {node}{COLOR_RESET}")
        else:
            # This case might happen if a primitive is directly in a list without an explicit label
            print(f"{indent_str}{prefix}{color}{node}{COLOR_RESET}")

def print_aligned_contact_info(contact_node, profile_indent_flags):
    """
    Helper function to print contact information aligned with the profile.
    """
    if "contact_info" in contact_node and isinstance(contact_node["contact_info"], dict):
        items_to_print = []
        contact_info_data = contact_node["contact_info"]

        # Add office_address lines first if present, and not None or empty string
        if "office_address" in contact_info_data and isinstance(contact_info_data["office_address"], list):
            for i, line in enumerate(contact_info_data["office_address"]):
                if line is not None and line != "": # Only add if not None or empty string
                    items_to_print.append((f"Address Line {i+1}", line))
        
        # Add other contact info items, excluding office_address, and not None or empty string
        for key, value in contact_info_data.items():
            if key != "office_address" and value is not None and value != "": # Only add if not office_address key and not None/empty string
                items_to_print.append((key, value))

        # Calculate the base indentation for contact info items.
        # This aligns with the profile name's indentation.
        contact_base_indent_parts = []
        if profile_indent_flags:
            # Add segments for all but the last flag
            for flag in profile_indent_flags[:-1]:
                contact_base_indent_parts.append("    " if flag else "│   ")
            # Add segment for the last flag (which corresponds to the profile's own prefix space)
            contact_base_indent_parts.append("    " if profile_indent_flags[-1] else "│   ")
        
        contact_item_base_indent_str = "".join(contact_base_indent_parts)
        
        for i, (key, value) in enumerate(items_to_print):
            is_last_contact = (i == len(items_to_print) - 1)
            contact_item_prefix = "└── " if is_last_contact else "├── "
            print(f"{contact_item_base_indent_str}{contact_item_prefix}{COLOR_GREEN}{key}: {value}{COLOR_RESET}")

def print_profile_names_colored(node, current_actual_depth=0, current_display_depth=0, indent_flags=None):
    """
    Recursively traverses the JSON to print any 'Name' fields found,
    color-coded by their structural depth in the JSON tree, with connecting lines.
    Also prints 'contact_info' if available, aligned with the profile.
    """
    if indent_flags is None:
        indent_flags = []

    color = get_color_for_depth(current_display_depth)
    
    # Calculate indentation and prefix for the current node's print line
    indent_str = "".join(["    " if flag else "│   " for flag in indent_flags[:-1]])
    current_node_prefix = "" # Default for root node, no prefix for the very first line
    if current_actual_depth > 0 or (indent_flags and current_actual_depth == 0):
        current_node_prefix = "└── " if (indent_flags and indent_flags[-1]) else "├── "

    printed_a_named_profile = False
    next_display_depth = current_display_depth # Default: display depth does not increment

    if isinstance(node, dict):
        profile_name_to_print = None
        
        # Check if this dictionary is a named profile
        if "profile_url" in node or "Name" in node:
            # Prioritize legal_name, then Name, then derive from profile_url
            profile_name_to_print = node.get("legal_name") or node.get("Name")
            if not profile_name_to_print and "profile_url" in node:
                profile_name_parts = node["profile_url"].split('/')
                profile_name_to_print = profile_name_parts[-2] if profile_name_parts[-1] == '' else profile_name_parts[-1]
            
            if profile_name_to_print and profile_name_to_print != "": # Only print if we found a name and it's not empty
                # Apply bold only for Depth 0
                bold_prefix = BOLD if current_display_depth == 0 else ""
                bold_suffix = RESET_BOLD if current_display_depth == 0 else ""

                # Removed "Profile (Depth {current_display_depth}):"
                print(f"{indent_str}{current_node_prefix}{bold_prefix}{color}{profile_name_to_print}{bold_suffix}{COLOR_RESET}")
                printed_a_named_profile = True
                next_display_depth = current_display_depth + 1 # Increment display depth only if a profile was printed

        if printed_a_named_profile:
            # Pass the current profile's indent_flags to the contact info printer for alignment
            print_aligned_contact_info(node, profile_indent_flags=indent_flags)

        # Gather all child dictionaries/lists for recursive processing, excluding contact_info itself
        children_for_recursion = []
        for key, value in node.items():
            if key != "contact_info" and isinstance(value, (dict, list)):
                children_for_recursion.append(value)
        
        # Recurse into children
        for i, child_node in enumerate(children_for_recursion):
            is_last_child = (i == len(children_for_recursion) - 1)
            # Pass current_actual_depth + 1 for the next level's structural indentation
            # Pass next_display_depth for the next level's printed depth number
            print_profile_names_colored(child_node, current_actual_depth + 1, next_display_depth, indent_flags + [is_last_child])

    elif isinstance(node, list):
        # Filter out None or empty string values from the list before recursing
        filtered_node = [item for item in node if item is not None and item != ""]

        # Recurse into each item in the filtered list.
        # Each item in a list is conceptually a child, so actual_depth increases.
        for i, item in enumerate(filtered_node):
            is_last_item_in_list = (i == len(filtered_node) - 1)
            # Pass current_actual_depth + 1 for the next level's structural indentation
            # Pass current_display_depth (not incremented) because the list itself isn't a named profile,
            # and its children should maintain the logical depth of their parent named profile.
            print_profile_names_colored(item, current_actual_depth + 1, current_display_depth, indent_flags + [is_last_item_in_list])


def main():
    parser = argparse.ArgumentParser(description="Process JSON data from a Pitchbook scraper output.")
    parser.add_argument(
        "--mode",
        choices=["tree", "names"],
        default="tree",
        help="Choose the display mode: 'tree' for full color-coded JSON tree, 'names' for only profile names color-coded by depth."
    )
    args = parser.parse_args()

    json_file_path = 'multi_company_pitchbook_data.json'

    # Check if the JSON file exists
    if not os.path.exists(json_file_path):
        print(f"{COLOR_RED}Error: JSON file not found at '{json_file_path}'. Please ensure the scraper has run and created the file.{COLOR_RESET}")
        return

    try:
        # Load the JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if args.mode == "tree":
            print(f"{COLOR_BLUE}--- Color Coded JSON Tree ---{COLOR_RESET}")
            # Start the recursive printing from the root data, with an empty list for initial indent flags
            print_json_tree_colored(data, []) 
            print(f"{COLOR_BLUE}--- End of Tree ---{COLOR_RESET}")
        elif args.mode == "names":
            print(f"{COLOR_BLUE}--- Profile Names by Depth ---{COLOR_RESET}")
            # Start actual_depth and display_depth at 0.
            # No initial indent_flags for the very first call.
            print_profile_names_colored(data, current_actual_depth=0, current_display_depth=0, indent_flags=[])
            print(f"{COLOR_BLUE}--- End of Names List ---{COLOR_RESET}")

    except json.JSONDecodeError as e:
        print(f"{COLOR_RED}Error decoding JSON from '{json_file_path}': {e}{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred: {e}{COLOR_RESET}")

if __name__ == "__main__":
    main()