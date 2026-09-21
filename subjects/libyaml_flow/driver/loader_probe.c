#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <yaml.h>

static void
print_hex(const unsigned char *data, size_t length)
{
    size_t i;

    if (data == NULL) {
        printf("-");
        return;
    }

    for (i = 0; i < length; i++) {
        printf("%02x", data[i]);
    }
}

static void
dump_document(yaml_document_t *document, int document_index)
{
    yaml_node_t *node;
    ptrdiff_t count;
    ptrdiff_t i;

    count =
        document->nodes.top -
        document->nodes.start;

    printf(
        "DOC %d nodes=%td\n",
        document_index,
        count
    );

    for (i = 0; i < count; i++) {
        node =
            document->nodes.start + i;

        printf(
            "NODE %td type=%d tag=",
            i + 1,
            (int)node->type
        );

        if (node->tag != NULL) {
            print_hex(
                node->tag,
                strlen(
                    (const char *)node->tag
                )
            );
        }
        else {
            printf("-");
        }

        if (node->type == YAML_SCALAR_NODE) {
            printf(
                " scalar_len=%zu value=",
                node->data.scalar.length
            );

            print_hex(
                node->data.scalar.value,
                node->data.scalar.length
            );
        }
        else if (
            node->type ==
            YAML_SEQUENCE_NODE
        ) {
            yaml_node_item_t *item;

            printf(" items=");

            for (
                item =
                    node->data.sequence.items.start;
                item <
                    node->data.sequence.items.top;
                item++
            ) {
                if (
                    item !=
                    node->data.sequence.items.start
                ) {
                    printf(",");
                }

                printf(
                    "%d",
                    (int)*item
                );
            }
        }
        else if (
            node->type ==
            YAML_MAPPING_NODE
        ) {
            yaml_node_pair_t *pair;

            printf(" pairs=");

            for (
                pair =
                    node->data.mapping.pairs.start;
                pair <
                    node->data.mapping.pairs.top;
                pair++
            ) {
                if (
                    pair !=
                    node->data.mapping.pairs.start
                ) {
                    printf(",");
                }

                printf(
                    "%d:%d",
                    (int)pair->key,
                    (int)pair->value
                );
            }
        }

        printf("\n");
    }
}

int
main(int argc, char **argv)
{
    FILE *input;
    yaml_parser_t parser;
    yaml_document_t document;
    yaml_node_t *root;
    int document_index = 0;

    if (argc != 2) {
        fprintf(
            stderr,
            "usage: %s INPUT.yaml\n",
            argv[0]
        );
        return 2;
    }

    input = fopen(
        argv[1],
        "rb"
    );

    if (input == NULL) {
        perror("fopen");
        return 2;
    }

    if (!yaml_parser_initialize(&parser)) {
        fprintf(
            stderr,
            "yaml_parser_initialize failed\n"
        );

        fclose(input);
        return 2;
    }

    yaml_parser_set_input_file(
        &parser,
        input
    );

    for (;;) {
        if (!yaml_parser_load(
                &parser,
                &document
            )) {

            fprintf(
                stderr,
                "parse_error=%d problem=%s "
                "line=%zu column=%zu\n",
                (int)parser.error,
                parser.problem != NULL
                    ? parser.problem
                    : "(none)",
                parser.problem_mark.line + 1,
                parser.problem_mark.column + 1
            );

            yaml_parser_delete(
                &parser
            );

            fclose(input);

            return 1;
        }

        root =
            yaml_document_get_root_node(
                &document
            );

        if (root == NULL) {
            yaml_document_delete(
                &document
            );

            break;
        }

        document_index++;

        dump_document(
            &document,
            document_index
        );

        yaml_document_delete(
            &document
        );
    }

    printf(
        "END documents=%d\n",
        document_index
    );

    yaml_parser_delete(
        &parser
    );

    fclose(input);

    return 0;
}
