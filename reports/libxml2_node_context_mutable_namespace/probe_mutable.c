#include <stdio.h>
#include <string.h>

#include <libxml/HTMLparser.h>
#include <libxml/parser.h>
#include <libxml/tree.h>

/* The shared Python input decoder passes the fragment followed by zero or
 * more prefix/URI pairs. An empty prefix denotes a default namespace.
 * No namespace URI, prefix, or enabling flag is fixed in this driver. */
int main(int argc, char **argv) {
    static const char html[] =
        "<html><body><div>context</div></body></html>";
    xmlDocPtr doc = NULL;
    xmlNodePtr root = NULL;
    xmlNodePtr list = NULL;
    xmlParserErrors result;
    int index;

    if (argc < 2 || (argc - 2) % 2 != 0) {
        fprintf(stderr, "usage: probe FRAGMENT [PREFIX URI]...\n");
        return 2;
    }
    doc = htmlReadMemory(html, (int)strlen(html), NULL, NULL,
                        HTML_PARSE_NOERROR | HTML_PARSE_NOWARNING);
    if (doc == NULL) {
        fprintf(stderr, "htmlReadMemory failed\n");
        return 2;
    }
    root = xmlDocGetRootElement(doc);
    if (root == NULL) {
        fprintf(stderr, "no root\n");
        xmlFreeDoc(doc);
        return 2;
    }
    for (index = 2; index < argc; index += 2) {
        const char *prefix = argv[index];
        const char *uri = argv[index + 1];
        if (xmlNewNs(root, BAD_CAST uri,
                     prefix[0] != '\0' ? BAD_CAST prefix : NULL) == NULL) {
            fprintf(stderr, "xmlNewNs failed\n");
            xmlFreeDoc(doc);
            return 2;
        }
    }
    result = xmlParseInNodeContext(root, argv[1], (int)strlen(argv[1]), 0, &list);
    printf("result=%d list=%s\n", (int)result,
           list != NULL ? "non-null" : "null");
    xmlFreeNodeList(list);
    xmlFreeDoc(doc);
    xmlCleanupParser();
    return 0;
}
