<?php
defined('_JEXEC') or die;

class plgAjaxJpcconnectorInstallerScript
{
    public function postflight($type, $parent)
    {
        if ($type !== 'install' && $type !== 'discover_install') {
            return true;
        }

        if (function_exists('random_bytes')) {
            $token = bin2hex(random_bytes(32));
        } else {
            $seed = JUserHelper::genRandomPassword(64)
                . microtime(true)
                . uniqid('', true);
            $token = hash('sha256', $seed);
        }

        $db = JFactory::getDbo();
        $query = $db->getQuery(true)
            ->select($db->quoteName(array('extension_id', 'params')))
            ->from($db->quoteName('#__extensions'))
            ->where($db->quoteName('type') . ' = ' . $db->quote('plugin'))
            ->where($db->quoteName('folder') . ' = ' . $db->quote('ajax'))
            ->where($db->quoteName('element') . ' = ' . $db->quote('jpcconnector'));
        $db->setQuery($query);
        $extension = $db->loadObject();

        if (!$extension) {
            JFactory::getApplication()->enqueueMessage(
                'JPC Connector установлен, но его настройки не найдены.',
                'warning'
            );
            return true;
        }

        $params = new JRegistry;
        $params->loadString((string) $extension->params);
        $params->set('token', $token);
        $extension->params = (string) $params;
        $extension->enabled = 1;
        $db->updateObject(
            '#__extensions',
            $extension,
            'extension_id',
            true
        );

        JFactory::getApplication()->enqueueMessage(
            '<strong>JPC Connector включён.</strong><br>'
            . 'Скопируйте token в настройки донора JPC:<br>'
            . '<code style="user-select:all">' . htmlspecialchars(
                $token,
                ENT_QUOTES,
                'UTF-8'
            ) . '</code><br>'
            . 'После первой успешной проверки подключения token '
            . 'будет заменён хешем.',
            'notice'
        );

        return true;
    }
}
